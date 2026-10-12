"""Chat header text; presentation never changes provider routing."""
from collections.abc import Mapping


def model_identity_text(name: str, provider: str, cfg: Mapping,
                        endpoint: str = '', backup: bool = False,
                        server_models: Mapping | None = None) -> str:
    if provider == 'local':
        return f'Model: {name} · AI trên máy'
    known = (server_models or {}).get(provider, '')
    custom = next((item.get('model', '') for item in cfg.get('custom_ai', [])
                   if item.get('id') == provider), '')
    variants = {'deepseek_flash': 'deepseek-flash', 'deepseek_pro': 'deepseek-v4-pro',
                'deepseek_r1': 'deepseek-flash'}
    # A backup's model cannot be inferred from the primary's configuration.
    model = known or ('' if backup else custom or variants.get(provider) or cfg.get(provider + '_model', ''))
    caption = 'Model trên server' if known else 'Model trong Cài đặt'
    identity = f'{caption}: {model}' if model else 'Model: chưa đọc được cấu hình server'
    server = endpoint or cfg.get('server_url', '')
    return f'{name} · {identity} · Server {"dự phòng" if backup else "kết nối"}: {server or "chưa kết nối"}'
