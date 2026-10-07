import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from assistant.storage import Store


class StartupTest(unittest.TestCase):
    def test_package_import_does_not_load_qt_or_ollama(self):
        result=subprocess.run([sys.executable,'-c',"import assistant,sys; assert not any(n.startswith(('PySide6','ollama')) for n in sys.modules)"],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_history_metadata_query_limits_and_filters_without_decoding_chats(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'history.db')
            ids=[]
            for owner in ('alice','bob'):
                for index in range(4):
                    cid=store.create(persist=False);state=store.load(cid)
                    state.update(account_username=owner,messages=[{'role':'user','content':f'{owner}-{index}','images':['large-image'*1000]}])
                    store.save(cid,state)
                    if owner=='alice':ids.append(cid)
            with patch('assistant.storage.json.loads',side_effect=AssertionError('Do not decode full chats for sidebar')):
                rows=store.list('alice',include_empty=False,limit=2)
            self.assertEqual(len(rows),2)
            self.assertTrue(all(cid in ids for cid,_ in rows))
            self.assertEqual(len(store.list('alice')),4)
            self.assertIsNone(store.conversation_title(ids[0],'bob'))
            self.assertTrue(store.conversation_title(ids[0],'alice').startswith('alice-'))
