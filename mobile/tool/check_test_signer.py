"""Verify the cached Android test identity before producing update APKs."""
import hashlib
import os
from pathlib import Path
import subprocess

EXPECTED='924eef2c1d8c1f4085aebb72fb8bbbacaec63a0c88a8680ebee6c1defc8218d9'


def main():
    path=Path.home()/'.android/debug.keystore'
    certificate=subprocess.check_output(['keytool','-exportcert','-keystore',str(path),'-storepass','android','-alias','androiddebugkey'],stderr=subprocess.DEVNULL)
    fingerprint=hashlib.sha256(certificate).hexdigest()
    print('Cached test signer SHA-256:',fingerprint)
    if fingerprint!=EXPECTED:
        raise SystemExit('Cached signer differs from the fixed test identity. Refusing to build with an unknown key.')
    with open(os.environ['GITHUB_ENV'],'a') as output:
        output.write('CHATAI_DEBUG_KEYSTORE='+str(path)+'\n')
        output.write('CHATAI_EXPECTED_SIGNER_SHA256='+EXPECTED+'\n')


if __name__=='__main__':main()
