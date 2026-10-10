"""Whether a model can read images, asked from the provider instead of a fixed table.

Local Ollama reports per-model capabilities (e.g. ['completion', 'tools', 'vision']);
any installed model that lists 'vision' may receive images.
"""
import json
from urllib.request import Request, urlopen

_CACHE = {}


def _show(host, model):
    request = Request(host.rstrip('/') + '/api/show', data=json.dumps({'model': model}).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read(2_000_000))


def local_supports_vision(host, model):
    """True when the CHAT_MODELS table says so or Ollama reports a 'vision' capability."""
    try:
        from .config import CHAT_MODELS
        if CHAT_MODELS.get(model, {}).get('vision'):
            return True
    except Exception:
        pass
    key = (host, model)
    if key not in _CACHE:
        try:
            info = _show(host, model)
            families = (info.get('details') or {}).get('families') or []
            _CACHE[key] = 'vision' in (info.get('capabilities') or []) or any(f in ('clip', 'mllama') for f in families)
        except Exception:
            return False  # not cached: Ollama may simply not be running yet
    return _CACHE[key]


def installed_vision_model(host):
    """First installed local model that can read images, or None."""
    try:
        with urlopen(host.rstrip('/') + '/api/tags', timeout=5) as response:
            names = [m.get('name') for m in json.loads(response.read(2_000_000)).get('models', [])]
    except Exception:
        return None
    return next((name for name in names if name and local_supports_vision(host, name)), None)
