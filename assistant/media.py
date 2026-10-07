from .modules import CHAT_MODELS, MEDIA_VARIANTS, media_model_dir
import gc
import uuid
import threading
import time
from datetime import datetime


def strip_reasoning_wrappers(value):
    """Remove hidden-reasoning and formatting wrappers from model output."""
    import re
    text=str(value or '').strip()
    text=re.sub(r'```\s*(?:text|prompt|english|chinese|json)?\s*', '', text, flags=re.I)
    text=text.replace('```','')
    text=re.sub(r'<think\b[^>]*>[\s\S]*?</think\s*>', ' ', text, flags=re.I)
    text=re.sub(r'<think\b[^>]*>[\s\S]*$', ' ', text, flags=re.I)
    text=re.sub(r'</?(?:answer|final|analysis)\b[^>]*>', ' ', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


def clean_generation_prompt(value):
    """Remove reasoning/format wrappers before a prompt reaches CLIP."""
    import re
    text=strip_reasoning_wrappers(value)
    text=re.sub(r'^\s*(?:(?:sure[,!]?\s*)?(?:here(?: is|\'s)\s+)?(?:the\s+)?(?:english|chinese|simplified chinese)?\s*(?:image|video)?\s*(?:generation\s+)?prompt|translation|提示词|英文提示词|中文提示词|中文翻译)\s*[:：]\s*', '', text, flags=re.I)
    text=re.sub(r'\s+', ' ', text).strip(' \t\r\n`\"\'')
    if not text:
        raise ValueError('Prompt rỗng sau khi loại phần suy luận của AI; không gửi prompt rác sang model ảnh.')
    if len(text)>2000:
        raise ValueError('Prompt tạo ảnh/video vượt quá 2000 ký tự.')
    return text


def to_english_prompt(client, text, *, model='qwen2.5:7b', num_ctx=4096, on_status=None, on_raw=None):
    """Translate user text to a short English prompt for the selected Turbo model."""
    import re
    from pathlib import Path
    on_status=on_status or (lambda _message:None)
    on_raw=on_raw or (lambda _model,_raw:None)
    system=(
        'Translate the user\'s image request into ONE short English prompt for Stable Diffusion. '
        'Put the main subject and requested count first. Preserve explicit details and do not invent subjects. '
        'Output only the prompt, with no analysis, explanation, or labels.'
    )
    last_error=None
    for attempt in range(2):
        if attempt:on_status('Bản dịch rỗng; đang thử dịch lại một lần…')
        try:
            response=client.chat(model=model,stream=False,keep_alive='10m',messages=[
                {'role':'system','content':system},
                {'role':'user','content':str(text)[:6000]}],
                options={'temperature':0.2,'num_ctx':min(4096,int(num_ctx or 4096)),'num_predict':120})
            message=response['message'] if isinstance(response,dict) else response.message
            raw=message.get('content','') if isinstance(message,dict) else getattr(message,'content','')
            # Keep the unmodified response for diagnosing prompt translation failures.
            # The log is local to this installation and is also useful for expert/tool paths.
            raw_record=f"[media-prompt-raw] model={model} attempt={attempt + 1} raw={raw!r}\n"
            print(raw_record, end='', flush=True)
            try:
                log_path=Path(__file__).resolve().parents[1] / 'data' / 'startup.log'
                log_path.parent.mkdir(parents=True,exist_ok=True)
                with log_path.open('a',encoding='utf-8') as log:log.write(raw_record)
            except OSError:
                pass
            on_raw(model,raw)
            # Remove a closed or truncated <think> block, then keep only the first
            # output line so explanations cannot consume CLIP's 77-token context.
            candidate=str(raw or '').strip()
            candidate=re.sub(r'<think\b[^>]*>[\s\S]*?</think\s*>',' ',candidate,flags=re.I)
            candidate=re.sub(r'<think\b[^>]*>[\s\S]*$',' ',candidate,flags=re.I)
            candidate=re.sub(r'</?(?:answer|final|analysis)\b[^>]*>',' ',candidate,flags=re.I)
            candidate=re.sub(r'```\s*(?:text|prompt|english)?\s*','',candidate,flags=re.I).replace('```','')
            cleaned=''
            for line in candidate.splitlines():
                if not line.strip():continue
                try:cleaned=clean_generation_prompt(line.strip())
                except ValueError:continue
                break
            cleaned=re.sub(r'^(?:prompt|translation|english prompt)\s*[:：]\s*','',cleaned,flags=re.I).strip()
            cleaned=cleaned.strip('"\'` ')[:200].strip()
            if cleaned:return cleaned
            last_error='Bản dịch rỗng sau khi làm sạch.'
        except Exception as error:
            last_error=str(error)
    raise RuntimeError('Không tạo được prompt tiếng Anh bằng '+model+' sau hai lần thử. '+str(last_error or ''))


# Reuse the loaded pipeline within the running desktop process. The cached
# pipeline stays on CPU between requests so Ollama can use the RTX 3070.
_PIPELINE_CACHE = {}
_PIPELINE_CACHE_LOCK = threading.Lock()


class MediaTools:
    def __init__(self, files, client, cfg, root, audit, on_status=None, model_variant='sd-turbo'):
        self.files, self.client, self.cfg, self.root, self.audit = files, client, cfg, root, audit
        self.on_status=on_status or (lambda _message: None)
        self.model_variant=model_variant if model_variant in MEDIA_VARIANTS else 'sd-turbo'

    def _phase(self,label,operation):
        """Keep the chat status alive during slow model imports and disk/VRAM loads."""
        started=time.monotonic();finished=threading.Event()
        def heartbeat():
            while not finished.wait(12):
                self.on_status(f'{label} · {int(time.monotonic()-started)} giây')
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
        try:return operation()
        finally:finished.set()

    def prepare(self, name, args):
        prompts = [args["prompt"]] if name == "image_generate" else args["prompts"]
        prompts=[clean_generation_prompt(prompt) for prompt in prompts]
        if not 1 <= len(prompts) <= 3 or any(not p.strip() or len(p) > 2000 for p in prompts):
            raise ValueError("Cần 1–3 prompt không rỗng, mỗi prompt tối đa 2000 ký tự.")
        return {"action": name, "prompts": prompts, "approval_id": uuid.uuid4().hex,
                "resolution": "512×512", "duration_seconds": max(6, 3*len(prompts)) if name == "video_generate" else None,
                "note": f"Dùng {MEDIA_VARIANTS[self.model_variant]['display']} local. Video là clip ảnh có zoom/pan. Model chat tạm unload để dành VRAM."}

    def commit(self, plan):
        self.on_status('Đang khởi tạo bộ tạo ảnh local…')
        torch=self._phase('Đang nạp PyTorch',lambda:__import__('torch'))
        AutoPipelineForText2Image=self._phase('Đang nạp Diffusers',
            lambda:__import__('diffusers',fromlist=['AutoPipelineForText2Image']).AutoPipelineForText2Image)
        if not torch.cuda.is_available():
            raise RuntimeError("Không thấy CUDA. Kiểm tra NVIDIA driver và PyTorch CUDA; không tự chuyển sang CPU chậm.")
        model_spec=MEDIA_VARIANTS[self.model_variant]
        folder = media_model_dir(self.root,self.model_variant)
        if not (folder / "ready.json").exists():
            raise RuntimeError("Model ảnh chưa tải. Bật module Ảnh/video trước.")
        # Không giữ Qwen và diffusion cùng VRAM. Ollama sẽ reload Qwen ở vòng chat sau.
        def release_chat_vram():
            try:loaded=self.client.ps().models
            except Exception as error:
                self.on_status('Không truy vấn được danh sách model Ollama: '+str(error)[:180])
                loaded=[]
            for model in loaded:
                if model.model in CHAT_MODELS:
                    try:self.client.generate(model=model.model,prompt='',keep_alive=0)
                    except Exception as error:self.on_status('Không giải phóng được '+model.model+': '+str(error)[:140])
        self._phase('Đang giải phóng VRAM khỏi AI trò chuyện',release_chat_vram)
        gc.collect();torch.cuda.empty_cache()
        output = self.files.path("outputs", exists=False)
        output.mkdir(parents=True, exist_ok=True)
        output = self.files.path(str(output))
        stamp = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        pipeline = None
        cache_key = str(folder.resolve())
        with _PIPELINE_CACHE_LOCK:
            pipeline = _PIPELINE_CACHE.pop(cache_key, None)
        cache_hit = pipeline is not None
        use_full_gpu = False
        images, paths = [], []
        self.audit("media_started", plan)
        try:
            def load_pipeline():
                return AutoPipelineForText2Image.from_pretrained(str(folder),local_files_only=True,
                    torch_dtype=torch.float16,variant='fp16',use_safetensors=True)
            if cache_hit:
                self.on_status('Dùng lại bộ tạo ảnh đã nạp sẵn trong RAM…')
            else:
                self.on_status('Đang nạp '+model_spec['display']+' từ ổ cục bộ… lần đầu có thể mất một lúc.')
                pipeline=self._phase('Đang nạp '+model_spec['display'],load_pipeline)
            free_vram,total_vram=torch.cuda.mem_get_info()
            use_full_gpu=free_vram>=int(5.0*1024**3)
            if use_full_gpu:
                torch.backends.cuda.matmul.allow_tf32=True
                try:
                    self._phase('Đang chuyển model lên RTX 3070',lambda:pipeline.to('cuda'))
                    self.on_status(f'Model đã nạp lên GPU · còn trống {torch.cuda.mem_get_info()[0]/1024**3:.1f} / {total_vram/1024**3:.1f} GB')
                except torch.cuda.OutOfMemoryError:
                    del pipeline;pipeline=None;gc.collect();torch.cuda.empty_cache()
                    self.on_status('VRAM đang bận; chuyển sang chế độ tiết kiệm bộ nhớ, sẽ chậm hơn.')
                    pipeline=self._phase('Đang nạp lại model ở chế độ tiết kiệm VRAM',load_pipeline)
                    pipeline.enable_model_cpu_offload()
                    use_full_gpu=False
            else:
                self.on_status(f'GPU chỉ còn {free_vram/1024**3:.1f} GB; dùng chế độ tiết kiệm VRAM, thời gian tạo sẽ lâu hơn.')
                pipeline.enable_model_cpu_offload()
            for i, prompt in enumerate(plan["prompts"]):
                started=time.monotonic()
                # Stable Diffusion's CLIP text encoder accepts 77 tokens. Explicitly
                # apply that exact text instead of allowing hidden reasoning or
                # trailing instructions to consume the context window.
                tokenizer=pipeline.tokenizer
                token_limit=getattr(tokenizer,'model_max_length',77)
                if not isinstance(token_limit,int) or token_limit>256:token_limit=77
                encoded=tokenizer(prompt,truncation=True,max_length=token_limit,return_tensors='pt')
                effective_prompt=tokenizer.decode(encoded.input_ids[0],skip_special_tokens=True).strip()
                if not effective_prompt:
                    raise RuntimeError('Prompt bị rỗng sau giới hạn token của model ảnh; không tạo ảnh ngẫu nhiên.')
                if effective_prompt!=prompt:
                    self.on_status(f'Prompt dài hơn giới hạn {token_limit} token; đã rút gọn đúng phần model ảnh thực sự đọc được.')
                self.audit('media_prompt_submitted',{'model':model_spec['display'],'prompt':effective_prompt,'token_limit':token_limit})
                self.on_status('Đang gửi prompt tới '+model_spec['display']+': '+effective_prompt[:180])
                def on_step_end(_pipe,step,_timestep,callback_kwargs):
                    self.on_status(f'Tạo ảnh {i+1}/{len(plan["prompts"])} · bước {step+1}/4 · {int(time.monotonic()-started)} giây')
                    return callback_kwargs
                def generate():
                    return pipeline(prompt=effective_prompt,num_inference_steps=4,guidance_scale=0.0,
                        height=512,width=512,callback_on_step_end=on_step_end).images[0]
                try:
                    image=generate()
                except torch.cuda.OutOfMemoryError:
                    if not use_full_gpu:raise
                    del pipeline;pipeline=None;gc.collect();torch.cuda.empty_cache()
                    self.on_status('SDXL-Turbo thiếu VRAM khi tạo ảnh; đang chuyển sang chế độ tiết kiệm bộ nhớ rồi thử lại…')
                    pipeline=self._phase('Đang nạp lại model tiết kiệm VRAM',load_pipeline)
                    pipeline.enable_model_cpu_offload();use_full_gpu=False
                    image=generate()
                path = output / f"image_{stamp}_{i+1}.png"
                image.save(path)
                images.append(image)
                paths.append(str(path))
            result = {"ok": True, "images": paths, "model": model_spec['display']}
            if plan["action"] == "video_generate":
                import os
                import numpy as np
                import imageio.v2 as imageio
                import imageio_ffmpeg
                from PIL import Image
                os.environ["IMAGEIO_FFMPEG_EXE"] = imageio_ffmpeg.get_ffmpeg_exe()
                video = output / f"video_{stamp}.mp4"
                fps = 12
                per_image = int(plan["duration_seconds"]*fps/len(images))
                with imageio.get_writer(str(video), fps=fps, codec="libx264", quality=7,
                                        macro_block_size=16, ffmpeg_log_level="error") as writer:
                    for image in images:
                        for frame in range(per_image):
                            fraction = frame / max(1, per_image-1)
                            size = int(512*(1+0.12*fraction))
                            scaled = image.resize((size, size), Image.Resampling.LANCZOS)
                            offset = int((size-512)*fraction)
                            picture = scaled.crop((offset, offset, offset+512, offset+512))
                            writer.append_data(np.asarray(picture))
                result.update(video=str(video), duration_seconds=plan["duration_seconds"],
                              note="MP4 từ ảnh AI có chuyển động máy ảnh; không phải video diffusion.")
            self.audit("media_success", result)
            self.on_status('Đã tạo ảnh xong; đang trả kết quả vào cuộc trò chuyện…')
            return result
        except Exception as exc:
            self.audit("media_failed", {"error": str(exc), "partial_images": paths})
            raise
        finally:
            if pipeline is not None:
                if use_full_gpu and self.model_variant=='sd-turbo':
                    try:
                        self._phase('Đang trả VRAM cho AI trò chuyện',lambda:pipeline.to('cpu'))
                        with _PIPELINE_CACHE_LOCK:
                            _PIPELINE_CACHE.clear()
                            _PIPELINE_CACHE[cache_key]=pipeline
                        self.on_status('Đã giữ bộ tạo ảnh trong RAM; lần tạo ảnh tiếp theo sẽ nạp nhanh hơn.')
                        pipeline=None
                    except Exception:
                        pass
                if pipeline is not None:
                    del pipeline
            gc.collect()
            torch.cuda.empty_cache()
