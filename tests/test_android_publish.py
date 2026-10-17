import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('android_publish',Path(__file__).resolve().parents[1]/'mobile/tool/publish_android.py')
publish=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

class AndroidPublishTests(unittest.TestCase):
    def test_versioned_apk_is_uploaded_before_compatible_update_pointer(self):
        digest='a'*64
        current={'version':'1.2.1','build':'56','file':'ChatAI-1.2.1-build56-abcdef0.apk','commit':'abcdef0','signature_verification':'certificate SHA-256 digest: '+digest}
        previous={**current,'build':'49','signature_verification':'certificate SHA-256 digest: '+'b'*64}
        calls=[];pointers=[]
        def run(command,**kwargs):
            calls.append(command)
            if command[:3]==['gh','release','upload'] and command[3].startswith('android-signed-'):
                pointers.append(json.loads(Path(command[4]).read_text()))
            return SimpleNamespace(returncode=1 if command[:3]==['gh','release','view'] else 0)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'build/verified-apk';output.mkdir(parents=True)
            (output/'build-info.json').write_text(json.dumps(current));(output/current['file']).write_bytes(b'apk')
            with patch.object(publish,'ROOT',root),patch.object(publish,'urlopen',return_value=io.BytesIO(json.dumps(previous).encode())),patch.object(publish.subprocess,'run',side_effect=run):
                publish.main()
        uploads=[c for c in calls if c[:3]==['gh','release','upload']]
        self.assertEqual(uploads[0][3],'android-1.2.1-build56')
        self.assertEqual(uploads[1][3],'android-signed-'+digest)
        self.assertEqual(pointers[0]['release_tag'],'android-1.2.1-build56')
        self.assertEqual(pointers[0]['signer_sha256'],digest)
        self.assertFalse(any(c[3]=='android-latest' for c in uploads))
