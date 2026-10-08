import json
from .modules import CHAT_MODELS
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if not cfg.get("server_url"):
        cfg["server_url"] = "https://chatai.anhvn53.workers.dev"
    if cfg.get('chat_font_revision') != 2:
        cfg['font_size']=13
        cfg['chat_font_revision']=2
        return save_config(cfg)
    return validate_config(cfg)


def validate_config(cfg):
    cfg = dict(cfg)
    from .windows_apps import validate_settings
    validate_settings(cfg)
    from .cloud import register_custom_ai
    cfg['custom_ai']=register_custom_ai(cfg.get('custom_ai',[]))
    cfg.setdefault("machine_profile","medium")
    cfg.setdefault("machine_auto_ai",True)
    cfg.setdefault("machine_profile_selected",False)
    cfg.setdefault("vision_model","gemma3:4b")
    if cfg['machine_profile'] not in ('weak','medium','high'):raise ValueError('Cấu hình máy không hợp lệ.')
    if type(cfg['machine_auto_ai']) is not bool:raise ValueError('Tự chọn AI phải là bật/tắt.')
    if not CHAT_MODELS.get(cfg['vision_model'],{}).get('vision'):raise ValueError('AI đọc ảnh không hỗ trợ ảnh.')
    cfg.setdefault("theme","dark")
    if cfg["theme"] not in ("light","dark"):raise ValueError("Giao diện chỉ hỗ trợ Sáng hoặc Tối.")
    if cfg.get('api_provider_revision') != 2:
        cfg['chat_provider']='deepseek_flash';cfg['api_provider_revision']=2
    cfg.setdefault("chat_provider","deepseek_flash")
    cfg.setdefault('nvidia_model','nvidia/llama-3.1-nemotron-ultra-253b-v1')
    if cfg.get('nvidia_model')=='meta/llama-3.3-70b-instruct':cfg['nvidia_model']='nvidia/llama-3.1-nemotron-ultra-253b-v1'
    cfg.setdefault('deepseek_model','deepseek-flash')
    cfg.setdefault('gemini_model','gemini-3.8-flash')
    import re
    for provider in ('nvidia','deepseek','gemini'):
        if not isinstance(cfg[provider+'_model'],str) or not re.fullmatch(r'[A-Za-z0-9._/-]{1,160}',cfg[provider+'_model']):raise ValueError('Tên model API không hợp lệ.')
    if cfg["chat_provider"] not in ("nvidia","deepseek","deepseek_flash","deepseek_pro","deepseek_r1","gemini","cloudflare","local") and cfg["chat_provider"] not in {x["id"] for x in cfg["custom_ai"]}:raise ValueError("Dịch vụ AI không hợp lệ.")
    for key,value in {"num_predict":2048,"font_size":13,"auto_python":True}.items():cfg.setdefault(key,value)
    cfg.setdefault('api_num_predict',4096)
    cfg.setdefault('api_temperature',min(1,cfg.get('temperature',.2)))
    if type(cfg['api_num_predict']) is not int or not 128<=cfg['api_num_predict']<=4096:
        raise ValueError('Token trực tuyến phải từ 128 đến 4096.')
    if isinstance(cfg['api_temperature'],bool) or not isinstance(cfg['api_temperature'],(int,float)) or not 0<=cfg['api_temperature']<=1:
        raise ValueError('Độ sáng tạo trực tuyến phải từ 0 đến 1.')
    server = urlparse(cfg.get('server_url',''))
    if cfg.get('server_url') and (server.scheme!='https' or not server.hostname or server.username or server.password or server.query or server.fragment or server.path not in ('','/')):
        raise ValueError('URL server phải là URL gốc HTTPS.')
    host = urlparse(cfg["ollama_host"])
    if (host.scheme != "http" or host.hostname not in {"localhost", "127.0.0.1", "::1"}
            or host.username or host.password or host.query or host.fragment
            or host.path not in {"", "/"}):
        raise ValueError("Ollama phải dùng địa chỉ HTTP loopback local.")
    # Chỉ cho phép model local trong danh mục phù hợp máy; không gọi model cloud.
    for key in ("default_model", "code_model"):
        if cfg[key] not in CHAT_MODELS:
            raise ValueError("Model không có trong danh mục local hỗ trợ.")
    if not 1024 <= cfg["num_ctx"] <= 32768:
        raise ValueError("num_ctx phải từ 1024 đến 32768.")
    if not 1 <= cfg["max_rounds"] <= 20:
        raise ValueError("max_rounds phải từ 1 đến 20.")
    if not 128 <= cfg.get('num_predict',2048) <= 8192 or not 0 <= cfg.get('temperature',.2) <= 2:
        raise ValueError('Token hoặc độ sáng tạo ngoài giới hạn.')
    if not 12 <= cfg.get('font_size',16) <= 22:
        raise ValueError('Cỡ chữ phải từ 12 đến 22.')
    roots = [(ROOT / p).resolve() for p in cfg["whitelist"]]
    if not roots:
        raise ValueError("Whitelist không được rỗng.")
    for path in roots:
        if (path == ROOT or path in ROOT.parents or path == Path(path.anchor)
                or path.is_relative_to(ROOT / "data")):
            raise ValueError("Không whitelist thư mục gốc, dự án, data hoặc thư mục cha.")
        path.mkdir(parents=True, exist_ok=True)
    cfg["roots"] = roots
    (ROOT / "data" / "backups").mkdir(parents=True, exist_ok=True)
    return cfg


def save_config(cfg):
    import shutil
    from datetime import datetime
    checked = validate_config(dict(cfg,chat_font_revision=2))
    path = ROOT / 'config.json'
    backup = ROOT / 'data/backups' / ('config-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    shutil.copy2(path,backup)
    payload = {k:v for k,v in checked.items() if k != 'roots'}
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)
    return checked


def remember_app_permission():
    """Persist only the app execution grant, preserving the saved configuration."""
    cfg=load_config()
    if not cfg.get('windows_apps_enabled'):
        raise PermissionError('Quyền điều khiển ứng dụng đã bị tắt; bật và lưu trước.')
    cfg['windows_apps_auto_execute']=True
    return save_config(cfg)
