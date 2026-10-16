"""Verify the cached Android test identity before producing update APKs."""
import hashlib
import os
from pathlib import Path
import subprocess

EXPECTED='16c911a4b2be0fe4e8ab7cf474f2247e94875330b84706b173f69f587f5c9b8f'


def main():
    path=Path.home()/'.android/debug.keystore'
    certificate=subprocess.check_output(['keytool','-exportcert','-keystore',str(path),'-storepass','android','-alias','androiddebugkey'],stderr=subprocess.DEVNULL)
    fingerprint=hashlib.sha256(certificate).hexdigest()
    print('Cached test signer SHA-256:',fingerprint)
    if fingerprint!=EXPECTED:
        raise SystemExit('Cached signer differs from published build 49. Refusing to publish an incompatible update.')
    with open(os.environ['GITHUB_ENV'],'a') as output:
        output.write('CHATAI_DEBUG_KEYSTORE='+str(path)+'\n')
        output.write('CHATAI_EXPECTED_SIGNER_SHA256='+EXPECTED+'\n')


if __name__=='__main__':main()
