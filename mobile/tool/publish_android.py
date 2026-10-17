"""Keep incompatible signing identities out of automatic Android updates."""
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]


def signer(info):
    matches=re.findall(r'certificate SHA-256 digest: (\w+)',info.get('signature_verification',''))
    return matches[0] if matches else None


def choose_tag(current,previous):
    if signer(current) and signer(current)==signer(previous):return 'android-latest'
    return f"android-{current['version']}-build{current['build']}"


def main():
    output=ROOT/'build/verified-apk'
    current=json.loads((output/'build-info.json').read_text())
    try:
        with urlopen('https://github.com/vuanh97nd/ChatAI/releases/download/android-latest/build-info.json',timeout=30) as response:
            previous=json.load(response)
    except Exception:
        previous={}
    # Roll back only the incompatible manifest published by this exact build;
    # never overwrite a concurrent update from another commit.
    if previous.get('file')=='ChatAI-1.0.1-build50-9908ca5.apk' and str(previous.get('commit','')).startswith('9908ca5'):
        baseline=ROOT/'tool/previous_android_update.json'
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'build-info.json';target.write_bytes(baseline.read_bytes())
            subprocess.run(['gh','release','upload','android-latest',str(target),'--clobber'],check=True)
        previous=json.loads(baseline.read_text())
    tag=choose_tag(current,previous)
    if subprocess.run(['gh','release','view',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        command=['gh','release','create',tag,'--target',current['commit'],'--title',f"Chat AI Android {current['version']} ({current['build']})",'--notes','APK đã kiểm thử. Bản ký khác bản cũ không thể cài đè; không gỡ bản cũ khi chưa sao lưu dữ liệu.']
        if tag!='android-latest':command.append('--prerelease')
        subprocess.run(command,check=True)
    subprocess.run(['gh','release','upload',tag,*[str(p) for p in output.iterdir()],'--clobber'],check=True)
    print('Published:',tag)
    if tag!='android-latest':print('Signing identity differs; existing automatic update manifest retained.')


if __name__=='__main__':main()
