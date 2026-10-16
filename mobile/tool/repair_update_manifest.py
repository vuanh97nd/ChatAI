"""Restore only a missing manifest or the exact incompatible APK from this task."""
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.request import urlopen


def main():
    release=json.loads(subprocess.check_output(['gh','release','view','android-latest','--json','assets']))
    asset=next((a for a in release['assets'] if a['name']=='build-info.json'),None)
    if asset:
        with urlopen(asset['url'],timeout=30) as response:current=json.load(response)
        if current.get('file')!='ChatAI-1.0.1-build50-9908ca5.apk' or not str(current.get('commit','')).startswith('9908ca5'):
            print('Existing manifest retained.');return
    baseline=Path(__file__).with_name('previous_android_update.json')
    with tempfile.TemporaryDirectory() as directory:
        target=Path(directory)/'build-info.json';target.write_bytes(baseline.read_bytes())
        subprocess.run(['gh','release','upload','android-latest',str(target),'--clobber'],check=True)
    print('Previous compatible update manifest restored; no APK or application data deleted.')


if __name__=='__main__':main()
