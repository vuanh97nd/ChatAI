"""Check the actual APK manifest/signature before uploading a named artifact."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def check_manifest(badging, version):
    name, code = version.split('+')
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging, re.M)
    if not package or package.groups() != ('vn.chatai.chatai_mobile', code, name):
        raise ValueError('APK package/version does not match pubspec.yaml')
    return name, code


def main():
    version = re.search(r'^version:\s*(\S+)', (ROOT / 'pubspec.yaml').read_text(), re.M).group(1)
    sdk = Path(os.environ.get('ANDROID_HOME') or os.environ['ANDROID_SDK_ROOT'])
    toolsets = [p for p in (sdk / 'build-tools').iterdir() if (p / 'aapt').is_file() and (p / 'apksigner').is_file()]
    tools = max(toolsets, key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.name)))
    apk = ROOT / 'build/app/outputs/flutter-apk/app-debug.apk'
    badging = subprocess.check_output([str(tools / 'aapt'), 'dump', 'badging', str(apk)], text=True)
    name, code = check_manifest(badging, version)
    signature = subprocess.check_output([str(tools / 'apksigner'), 'verify', '--verbose', '--print-certs', str(apk)], text=True)
    commit = os.environ['GITHUB_SHA']
    output = ROOT / 'build/verified-apk'
    output.mkdir(parents=True, exist_ok=True)
    filename = f'ChatAI-{name}-build{code}-{commit[:7]}.apk'
    shutil.copyfile(apk, output / filename)
    metadata = {'file': filename, 'version': name, 'build': code, 'commit': commit,
                'sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
                'signature_verification': signature,
                'run': f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"}
    (output / 'build-info.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    summary = f'### Verified ChatAI APK\n\nVersion: **{name} ({code})**\n\nCommit: `{commit}`\n\nFile: `{filename}`\n\nSHA-256: `{metadata["sha256"]}`\n'
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write(summary)
    print(summary)


if __name__ == '__main__':
    main()
