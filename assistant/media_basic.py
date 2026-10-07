"""Safe, built-in image resizing and slideshow video tools using light Python packages."""
import uuid
from datetime import datetime
from pathlib import Path

from .excel import digest


class BasicMediaTools:
    IMAGE_EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp'}

    def __init__(self,files,audit):
        self.files,self.audit=files,audit

    def prepare(self,name,args):
        if name=='image_resize':
            source=self.files.path(args['path'])
            if not source.is_file() or source.suffix.lower() not in self.IMAGE_EXTENSIONS:
                raise ValueError('Chỉ xử lý ảnh PNG, JPG, WEBP hoặc BMP trong whitelist.')
            width,height=args['width'],args['height']
            if type(width) is not int or type(height) is not int or not 64<=width<=4096 or not 64<=height<=4096:
                raise ValueError('Kích thước ảnh cần từ 64 đến 4096 px mỗi chiều.')
            if source.stat().st_size>30*1024**2:raise ValueError('Ảnh đầu vào tối đa 30 MiB.')
            inputs=[{'path':str(source),'name':source.name,'sha256':digest(source)}]
            params={'width':width,'height':height}
        elif name=='video_from_images':
            raw=args['image_paths'];seconds=args['seconds_per_image']
            if not isinstance(raw,list) or not 1<=len(raw)<=8:raise ValueError('Chọn từ 1 đến 8 ảnh.')
            if type(seconds) is not int or not 2<=seconds<=8:raise ValueError('Mỗi ảnh cần hiển thị từ 2 đến 8 giây.')
            inputs=[];seen=set();total=0
            for value in raw:
                source=self.files.path(value)
                if not source.is_file() or source.suffix.lower() not in self.IMAGE_EXTENSIONS:
                    raise ValueError('Mọi đầu vào phải là ảnh PNG, JPG, WEBP hoặc BMP trong whitelist.')
                if source.name.casefold() in seen:raise ValueError('Danh sách có ảnh trùng tên.')
                seen.add(source.name.casefold());total+=source.stat().st_size
                if total>30*1024**2:raise ValueError('Tổng ảnh đầu vào tối đa 30 MiB.')
                inputs.append({'path':str(source),'name':source.name,'sha256':digest(source)})
            params={'seconds_per_image':seconds,'fps':12,'resolution':'1280×720'}
        else:raise ValueError('Thao tác ảnh/video cơ bản không được hỗ trợ.')
        return {'action':name,'inputs':inputs,**params,'approval_id':uuid.uuid4().hex,
                'output':'workspace/outputs','description':'Tạo file mới, không ghi đè ảnh nguồn. Video là slideshow MP4 có chuyển động zoom/pan, không phải video diffusion.'}

    def commit(self,plan):
        import numpy as np
        import imageio.v2 as imageio
        import imageio_ffmpeg
        from PIL import Image,ImageOps
        from tempfile import TemporaryDirectory

        folder=self.files.path('outputs',exists=False);folder.mkdir(parents=True,exist_ok=True)
        stamp=f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        self.audit('media_basic_started',plan)
        result={'ok':False,'action':plan['action']}
        with TemporaryDirectory(prefix='chat_ai_media_') as raw:
            snapshot=Path(raw);sources=[]
            for record in plan['inputs']:
                source=self.files.path(record['path'])
                if digest(source)!=record['sha256']:raise RuntimeError('Ảnh nguồn đã đổi; hãy gửi yêu cầu lại.')
                copy=snapshot/record['name'];copy.write_bytes(source.read_bytes());sources.append(copy)
            if plan['action']=='image_resize':
                target=self.files.path(str(folder/f"image_{stamp}.png"),exists=False)
                with Image.open(sources[0]) as image:
                    image=ImageOps.exif_transpose(image).convert('RGB').resize((plan['width'],plan['height']),Image.Resampling.LANCZOS)
                    image.save(target,format='PNG',optimize=True)
            else:
                import os
                os.environ['IMAGEIO_FFMPEG_EXE']=imageio_ffmpeg.get_ffmpeg_exe()
                target=self.files.path(str(folder/f"video_{stamp}.mp4"),exists=False)
                width,height,fps=1280,720,plan['fps'];frames_per=plan['seconds_per_image']*fps
                with imageio.get_writer(str(target),fps=fps,codec='libx264',quality=6,macro_block_size=16,ffmpeg_log_level='error') as writer:
                    for source in sources:
                        with Image.open(source) as raw_image:
                            base=ImageOps.fit(ImageOps.exif_transpose(raw_image).convert('RGB'),(width,height),method=Image.Resampling.LANCZOS)
                        for frame in range(frames_per):
                            progress=frame/max(1,frames_per-1);scale=1.0+0.08*progress
                            sw,sh=int(width*scale),int(height*scale)
                            enlarged=base.resize((sw,sh),Image.Resampling.LANCZOS)
                            dx,dy=sw-width,sh-height
                            left=int(dx*(progress if len(sources)%2 else 1-progress));top=int(dy*progress)
                            writer.append_data(np.asarray(enlarged.crop((left,top,left+width,top+height))))
            result.update(ok=True,files=[str(target)],resolution=plan.get('resolution',f"{plan.get('width')}×{plan.get('height')}"),
                          note='Đã tạo file mới trong workspace/outputs bằng thư viện Python cơ bản; không dùng model sinh ảnh/video.')
        self.audit('media_basic_success',result)
        return result
