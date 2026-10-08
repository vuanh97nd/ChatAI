"""Cập nhật từ GitHub Releases; tải có xác nhận, không tự thực thi bộ cài."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CURRENT_VERSION = '2.6.6'
REPOSITORY = 'vuanh97nd/ChatAI'
RELEASES_URL = 'https://github.com/' + REPOSITORY + '/releases'
API_URL = 'https://api.github.com/repos/' + REPOSITORY + '/releases/latest'
MAX_DOWNLOAD = 500 * 1024 * 1024

def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)(?:\.(\d+))?', str(value).strip())
    if not match:
        raise ValueError('Release cần tag dạng v2.6.6, không phải bản thử nghiệm.')
    return tuple(int(x or 0) for x in match.groups())

def parse_release(data):
    if not isinstance(data,dict) or data.get('draft') or data.get('prerelease'):
        raise ValueError('Chỉ dùng release chính thức đã công bố.')
    tag = str(data.get('tag_name',''))
    latest = version_tuple(tag)
    assets = []
    for asset in data.get('assets',[]):
        name = str(asset.get('name',''))
        url = str(asset.get('browser_download_url',''))
        p = urlparse(url)
        if (not re.fullmatch(r'(?:Chat-AI|ChatAI)-(?:Setup-)?[A-Za-z0-9._-]+\.(?:exe|zip)',name)
                or p.scheme!='https' or p.netloc!='github.com' or not p.path.startswith('/'+REPOSITORY+'/releases/download/')
                or p.query or p.fragment):
            continue
        size = asset.get('size',0)
        if not isinstance(size,int) or not 0<size<=MAX_DOWNLOAD:
            continue
        digest = str(asset.get('digest') or '')
        if digest and not re.fullmatch('sha256:[a-fA-F0-9]{64}',digest):
            continue
        assets.append(dict(name=name,url=url,size=size,sha256=digest.split(':')[-1].lower() if digest else None))
    assets.sort(key=lambda a:(not a['name'].lower().endswith('.exe'),a['name']))
    return dict(version=tag,newer=latest>version_tuple(CURRENT_VERSION),notes=str(data.get('body') or '')[:20000],
                url=RELEASES_URL,asset=assets[0] if assets else None)

def check_latest():
    request=Request(API_URL,headers={'Accept':'application/vnd.github+json','User-Agent':'Chat-AI/'+CURRENT_VERSION,'X-GitHub-Api-Version':'2022-11-28'})
    try:
        with urlopen(request,timeout=20) as response:
            raw=response.read(1000001)
        if len(raw)>1000000:raise ValueError('Metadata release quá lớn.')
        return parse_release(json.loads(raw))
    except HTTPError as error:
        if error.code==404:raise RuntimeError('Chưa đọc được release công khai. Repo cần public và có GitHub Release chính thức.') from None
        if error.code in (403,429):raise RuntimeError('GitHub đang giới hạn yêu cầu. Thử lại sau.') from None
        raise RuntimeError('GitHub HTTP '+str(error.code)) from None
    except (URLError,TimeoutError):raise RuntimeError('Không kết nối được GitHub. Kiểm tra mạng.') from None

def download_asset(asset,directory,progress=lambda text:None):
    # Kiểm tra lại asset kể cả khi hàm được gọi trực tiếp.
    checked=parse_release({'tag_name':CURRENT_VERSION,'assets':[{'name':asset['name'],'browser_download_url':asset['url'],'size':asset['size'],'digest':'sha256:'+asset['sha256'] if asset.get('sha256') else None}]})['asset']
    if not checked:raise ValueError('File cập nhật ngoài danh mục GitHub của Chat AI.')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    target=directory/checked['name'];part=target.with_suffix(target.suffix+'.part')
    sha=hashlib.sha256();count=0;started=time.monotonic();last=started
    request=Request(checked['url'],headers={'User-Agent':'Chat-AI/'+CURRENT_VERSION})
    try:
        with urlopen(request,timeout=120) as response,part.open('wb') as output:
            final=urlparse(response.geturl())
            if final.scheme!='https' or final.hostname not in {'github.com','objects.githubusercontent.com','release-assets.githubusercontent.com'}:
                raise RuntimeError('Nguồn file cập nhật không hợp lệ.')
            while True:
                if time.monotonic()-started>3600:raise TimeoutError('Tải cập nhật quá thời gian.')
                chunk=response.read(256*1024)
                if not chunk:break
                count+=len(chunk)
                if count>MAX_DOWNLOAD or count>checked['size']:raise RuntimeError('Kích thước tải không hợp lệ.')
                output.write(chunk);sha.update(chunk)
                current=time.monotonic()
                if current-last>=1:
                    speed=count/max(.001,current-started)
                    progress(f'Đang tải: {count/1e6:.1f}/{checked["size"]/1e6:.1f} MB · {speed/1e6:.1f} MB/s')
                    last=current
        if count!=checked['size']:raise RuntimeError('File tải chưa đủ. Hãy thử lại.')
        digest=sha.hexdigest()
        if checked['sha256'] and digest!=checked['sha256']:raise RuntimeError('SHA-256 không khớp; đã loại bỏ file tải.')
        part.replace(target)
        target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n',encoding='ascii')
        return dict(path=str(target),sha256=digest,verified=bool(checked['sha256']))
    except Exception:
        part.unlink(missing_ok=True)
        raise
