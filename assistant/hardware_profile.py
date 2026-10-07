"""Machine profiles and installed-model choices; detection never downloads anything.

Bản 2026-10-07: ưu tiên Qwen3 8B (kết quả đánh giá tốt hơn, không lẫn tiếng Trung) và
dùng ngữ cảnh 8192 cho máy Trung bình (RTX 3070 8 GB đủ chạy).
"""
import os
import platform
import shutil
import subprocess

LABELS={'weak':'Yếu','medium':'Trung bình','high':'Cao'}


def detect_hardware():
    info={'cpu':platform.processor() or platform.machine(),'cpu_threads':os.cpu_count() or 1,'ram_gb':None,'gpu':'Chưa nhận diện GPU','vram_gb':None}
    try:
        if os.name=='nt':
            import ctypes
            class Memory(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in ('total','available','total_page','available_page','total_virtual','available_virtual','extended')]
            memory=Memory();memory.length=ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):info['ram_gb']=round(memory.total/1024**3,1)
        elif hasattr(os,'sysconf'):
            info['ram_gb']=round(os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')/1024**3,1)
    except (OSError,ValueError,AttributeError):pass
    executable=shutil.which('nvidia-smi')
    if executable:
        try:
            result=subprocess.run([executable,'--query-gpu=name,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
            devices=[]
            for line in result.stdout.splitlines():
                name,memory=line.rsplit(',',1);devices.append((float(memory.strip())/1024,name.strip()))
            if devices:
                vram,name=max(devices);info.update(gpu=name,vram_gb=round(vram,1))
        except (OSError,ValueError,subprocess.SubprocessError):pass
    return info


def inferred_level(info):
    ram=info.get('ram_gb') or 0;vram=info.get('vram_gb') or 0
    if ram>=32 and vram>=12:return 'high'
    if ram>=16 or (ram>=8 and vram>=6):return 'medium'
    return 'weak' if ram else 'medium'


def recommendations(level,info=None):
    info=info or {};level=level if level in LABELS else 'medium'
    values={
        'weak':{'chat':['qwen2.5:1.5b','qwen2.5:3b'],'code':['qwen2.5-coder:3b','qwen2.5:1.5b','qwen2.5:3b'],'num_ctx':2048,'num_predict':768},
        'medium':{'chat':['qwen3:8b','qwen2.5:7b','qwen2.5:3b','qwen2.5:1.5b'],'code':['qwen2.5-coder:7b','qwen3:8b','qwen2.5-coder:3b','qwen2.5:7b','qwen2.5:3b','qwen2.5:1.5b'],'num_ctx':8192,'num_predict':2048},
        'high':{'chat':['qwen3:8b','qwen2.5:7b','qwen2.5:3b','qwen2.5:1.5b'],'code':['qwen2.5-coder:7b','qwen3:8b','qwen2.5-coder:3b','qwen2.5:7b','qwen2.5:3b','qwen2.5:1.5b'],'num_ctx':8192,'num_predict':2048}}
    result=dict(values[level]);result['chat']=list(result['chat']);result['code']=list(result['code']);result['vision']=['gemma3:4b']
    if level=='high' and (info.get('ram_gb') or 0)>=48 and (info.get('vram_gb') or 0)>=24:
        result['code'].insert(0,'qwen2.5-coder:32b')
    result['note']={
        'weak':'Ưu tiên AI nhỏ, tiết kiệm bộ nhớ. Đọc ảnh Gemma 4B cần thêm bộ nhớ; có thể chậm trên máy yếu.',
        'medium':'Cân bằng tốc độ và chất lượng. RAM 16 GB / RTX 3070 8 GB phù hợp mức này: Qwen3 8B, ngữ cảnh 8192.',
        'high':'Ưu tiên ngữ cảnh dài. AI 32B chỉ được gợi ý khi nhận diện đủ RAM và VRAM.'}[level]
    return result


def available_choice(priority,installed):
    names=set(installed or [])
    names|={name.removesuffix(':latest') for name in names}
    return next((model for model in priority if model in names),None)
