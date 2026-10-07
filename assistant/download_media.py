"""Resumable SD-Turbo / SDXL-Turbo download in the installer process."""
import json
import os
import sys
import time
from pathlib import Path


def main():
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','180')
    os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','60')
    # Conservative HTTP transfer on networks where the Xet client is interrupted.
    os.environ.setdefault('HF_HUB_DISABLE_XET','1')
    import requests
    import threading
    from tqdm.auto import tqdm
    class DownloadProgress(tqdm):
        tracked={};lock=threading.RLock();last=0;previous=0;previous_time=time.monotonic()
        def update(self,n=1):
            result=super().update(n)
            if self.unit=='B' and self.total:
                with self.lock:
                    type(self).tracked[id(self)]=(self.n,self.total)
                    current=time.monotonic()
                    if current-type(self).last>=1:
                        completed=sum(x[0] for x in self.tracked.values());total=sum(x[1] for x in self.tracked.values())
                        rate=max(0,completed-type(self).previous)/max(.1,current-type(self).previous_time)
                        print('CHAT_AI_PROGRESS '+json.dumps({'completed':completed,'total':total,'rate':rate}),flush=True)
                        type(self).last=current;type(self).previous=completed;type(self).previous_time=current
            return result
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from huggingface_hub import snapshot_download,configure_http_backend
    def backend():
        session=requests.Session()
        retry=Retry(total=4,connect=4,read=4,backoff_factor=1,
                    status_forcelist=[429,500,502,503,504],allowed_methods=['GET','HEAD'])
        session.mount('https://',HTTPAdapter(max_retries=retry))
        return session
    configure_http_backend(backend_factory=backend)
    folder=Path(sys.argv[1]);folder.mkdir(parents=True,exist_ok=True)
    variant=sys.argv[2] if len(sys.argv)>2 else 'sd-turbo'
    variants={
        'sd-turbo':{
            'repo':'stabilityai/sd-turbo','label':'SD-Turbo FP16',
            'required':['model_index.json','unet/diffusion_pytorch_model.fp16.safetensors',
                'vae/diffusion_pytorch_model.fp16.safetensors','text_encoder/model.fp16.safetensors',
                'tokenizer/vocab.json','tokenizer/merges.txt','scheduler/scheduler_config.json']},
        'sdxl-turbo':{
            'repo':'stabilityai/sdxl-turbo','label':'SDXL-Turbo FP16',
            'required':['model_index.json','unet/diffusion_pytorch_model.fp16.safetensors',
                'vae/diffusion_pytorch_model.fp16.safetensors','text_encoder/model.fp16.safetensors',
                'text_encoder_2/model.fp16.safetensors','tokenizer/vocab.json','tokenizer/merges.txt',
                'tokenizer_2/vocab.json','tokenizer_2/merges.txt','scheduler/scheduler_config.json']},
    }
    if variant not in variants:raise ValueError('Phiên bản model ảnh không hợp lệ.')
    spec=variants[variant]
    for attempt in range(4):
        try:
            print(f'Tải {spec["label"]}: lần {attempt+1}/4; tiếp tục các file đã tải.',flush=True)
            snapshot_download(repo_id=spec['repo'],local_dir=str(folder),
                allow_patterns=['model_index.json','**/*.json','**/*.txt','**/*.fp16.safetensors'],
                max_workers=2 if attempt==0 else 1,tqdm_class=DownloadProgress)
            missing=[name for name in spec['required'] if not (folder/name).is_file()]
            if missing:raise RuntimeError('Model chưa đủ file: '+', '.join(missing))
            (folder/'ready.json').write_text(json.dumps({'repo':spec['repo'],'variant':'fp16'}),encoding='utf-8')
            print(spec['label']+' đã tải đầy đủ.',flush=True);return
        except requests.RequestException as error:
            status=getattr(getattr(error,'response',None),'status_code',None)
            if status in (401,403,404) or attempt==3:raise
            print('Kết nối Hugging Face bị ngắt; sẽ thử lại với một luồng.',flush=True)
            time.sleep(min(5*(attempt+1),15))

if __name__=='__main__':main()
