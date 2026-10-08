"""Update an existing Cloudflare Worker without replacing its bindings or secrets."""
import json
import os
from pathlib import Path
import re
import secrets
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def multipart(source, settings):
    bindings = settings.get('bindings')
    if not isinstance(bindings, list):
        raise ValueError('Cloudflare did not return bindings; refusing to deploy.')
    types = sorted({binding['type'] for binding in bindings})
    metadata = {'main_module': 'work.js', 'keep_bindings': types,
                'compatibility_date': settings['compatibility_date']}
    for key in ('compatibility_flags', 'limits', 'observability'):
        if key in settings:
            metadata[key] = settings[key]
    boundary = 'ChatAI-' + secrets.token_hex(16)
    parts = []
    for name, filename, mime, data in (
        ('metadata', None, 'application/json', json.dumps(metadata).encode()),
        ('work.js', 'work.js', 'application/javascript+module', source),
    ):
        header = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename:
            header += f'; filename="{filename}"'
        parts.append((header + f'\r\nContent-Type: {mime}\r\n\r\n').encode() + data + b'\r\n')
    return b''.join(parts) + f'--{boundary}--\r\n'.encode(), 'multipart/form-data; boundary=' + boundary


def deploy(env=os.environ, request=urlopen):
    token = env.get('CF_API_TOKEN', '')
    account = env.get('CF_ACCOUNT_ID', '')
    worker = env.get('CF_WORKER_NAME', 'chatai')
    if not token or not re.fullmatch(r'[a-fA-F0-9]{32}', account):
        raise ValueError('Add GitHub Actions secrets CF_API_TOKEN and CF_ACCOUNT_ID before deployment.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', worker):
        raise ValueError('Invalid CF_WORKER_NAME repository variable.')
    url = f'https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/{worker}'
    headers = {'Authorization': 'Bearer ' + token}
    def call(req):
        try:
            with request(req, timeout=120) as response:
                result = json.load(response)
        except HTTPError as error:
            # Never print request headers, tokens or remote response bodies.
            raise RuntimeError(f'Cloudflare HTTP {error.code}; check token permissions and existing Worker name.') from None
        if not result.get('success'):
            codes = [str(item.get('code', 'unknown')) for item in result.get('errors', [])]
            raise RuntimeError('Cloudflare rejected deployment; error codes: ' + ', '.join(codes))
        return result['result']
    settings = call(Request(url + '/settings', headers=headers))
    source = Path(__file__).resolve().parents[1].joinpath('work.js').read_bytes()
    body, content_type = multipart(source, settings)
    call(Request(url, data=body, headers={**headers, 'Content-Type': content_type}, method='PUT'))
    print(f'Deployed work.js to existing Worker {worker}; retained binding types and secrets.')


if __name__ == '__main__':
    deploy()
