"""Build on Windows with Python 3.12 x64. Produce a relocatable full runtime."""
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def run(args):
    subprocess.run([str(arg) for arg in args],check=True,cwd=ROOT)


def assets():
    from PIL import Image,ImageDraw,ImageFont
    folder=ROOT/'installer-assets';folder.mkdir(exist_ok=True)
    with Image.open(ROOT/'logo_chat_ai.png') as original:
        logo=original.convert('RGBA')
    icon=Image.new('RGBA',(256,256));thumb=logo.copy();thumb.thumbnail((240,240))
    icon.alpha_composite(thumb,((256-thumb.width)//2,(256-thumb.height)//2))
    icon.save(folder/'chat_ai.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    for name,size,box,y in [('wizard.bmp',(164,314),120,64),('wizard-small.bmp',(55,55),45,5)]:
        image=Image.new('RGB',size,(25,28,46) if size[0]>55 else (255,255,255))
        thumb=logo.copy();thumb.thumbnail((box,box))
        image.paste(thumb,((size[0]-thumb.width)//2,y),thumb)
        if size[0]>55:
            fontpath=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts/segoeuib.ttf'
            font=ImageFont.truetype(str(fontpath),20) if fontpath.exists() else ImageFont.load_default()
            draw=ImageDraw.Draw(image);draw.text((82,220),'Chat AI',font=font,fill='white',anchor='mm')
        image.save(folder/name)


def main():
    if os.name!='nt' or sys.version_info[:2]!=(3,12) or struct.calcsize('P')!=8:
        raise RuntimeError('Build yêu cầu Windows và Python 3.12 64-bit trên máy build.')
    if sys.version_info[:3] < (3,12,10):
        raise RuntimeError('Build cần Python 3.12.10 trở lên trong nhánh 3.12 để tránh lỗi tương thích six/Qt.')
    base=Path(sys.base_prefix).resolve()
    target=ROOT/'runtime/python'
    if not (base/'python.exe').is_file() or not (base/'Lib/ensurepip').is_dir():
        raise RuntimeError('Cần Python 3.12 bản đầy đủ từ python.org trên máy build.')
    # Source installation must be outside output to avoid recursive copying.
    if base==target.resolve() or base.is_relative_to(target.resolve()):
        raise RuntimeError('Không dùng chính runtime đầu ra để build lại.')
    stage=ROOT/'runtime/python.building'
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for item in base.iterdir():
        if item.name.lower() in ('scripts','doc','tools','include','libs','__pycache__','pyvenv.cfg'):continue
        dest=stage/item.name
        if item.is_dir():
            shutil.copytree(item,dest,ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc','test','tests','idlelib'))
        else:shutil.copy2(item,dest)
    python=stage/'python.exe'
    run([python,'-m','ensurepip','--upgrade'])
    run([python,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:','-r',ROOT/'requirements-bundled.txt'])
    run([python,'-c','import PySide6.QtWidgets,ollama,pypdf,pypdfium2,PIL,imageio,cv2; import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe()); print("Bundled imports OK")'])
    manifest={'python':sys.version,'version':'2.6.6','bundled':True,'requirements':'requirements-bundled.txt'}
    (stage/'chat-ai-runtime.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    freeze=subprocess.check_output([str(python),'-m','pip','freeze'],text=True)
    (stage/'bundled-packages.txt').write_text(freeze,encoding='utf-8')
    if target.exists():shutil.rmtree(target)
    stage.rename(target)
    # Verify after relocation too, not just before the rename.
    run([target/'python.exe','-c','import PySide6.QtWidgets,ollama,pypdf,pypdfium2,PIL,imageio,cv2; import imageio_ffmpeg,sys; print(imageio_ffmpeg.get_ffmpeg_exe()); print(sys.prefix)'])
    run([target/'python.exe','-c','import runpy; runpy.run_path("build_runtime.py")["assets"]()'])
    csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not csc.exists():
        csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework/v4.0.30319/csc.exe'
    if not csc.exists():raise RuntimeError('Máy build thiếu C# compiler .NET Framework 4.x. Cài .NET Framework Developer Pack.')
    run([csc,'/nologo','/target:winexe','/reference:System.Windows.Forms.dll',
         '/win32icon:'+str(ROOT/'installer-assets/chat_ai.ico'),'/out:'+str(ROOT/'ChatAI.exe'),ROOT/'ChatAI-Launcher.cs'])
    print('Runtime, ChatAI.exe và icon/logo sẵn sàng. Không cần Python trên máy người dùng.')


if __name__=='__main__':main()
