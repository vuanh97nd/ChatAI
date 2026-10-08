import json
import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.document_memory import DocumentMemory
from assistant.history_sync import HistorySync
from assistant.plaxis_confirmation import confirmation_call
from tests.test_history_sync import Backend

PROPOSAL="""Đây là bài 'Drained and undrained stability of an embankment'. Bờ đắp cao 4 m, đỉnh rộng 2,0 m. Tôi sẽ tạo script đúng đề bài. Bạn xác nhận nhé?"""

class DocumentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'a.db')
        self.memory=DocumentMemory(self.store)
    def test_read_excerpts_survive_restart_without_original_file(self):
        self.memory.remember('alice',[{'file':'C:/missing/tutorial.pdf','text':'Bờ đắp cao 4 m','coverage':'partial','coverage_note':'Trang 1–4'}])
        self.memory.remember('alice',[{'file':'C:/missing/tutorial.pdf','text':'E50 = 5600','range_start':5,'coverage':'partial'}])
        restored=DocumentMemory(Store(self.store.path))
        context=restored.context('alice','bờ đắp')
        self.assertIn('Bờ đắp cao 4 m',context);self.assertIn('E50 = 5600',context)
        self.assertIn('tutorial.pdf',context);self.assertEqual(restored.context('bob','bờ đắp'),'')
    def test_cloud_restore_includes_document_and_accepted_task(self):
        self.memory.remember('alice',[{'file':'tutorial.pdf','text':'Hardening Soil: E50 = 5600'}])
        state={'account_username':'alice','messages':[{'role':'assistant','content':PROPOSAL},{'role':'user','content':'ok'}]}
        call=confirmation_call('ok',state,True,True)
        self.assertEqual(call['function']['name'],'plaxis_run_problem')
        problem=json.loads(call['function']['arguments']['problem'])
        self.assertEqual(problem['type'],'embankment_stability')
        cid=self.store.create(False);self.store.save(cid,state)
        backend=Backend();session={'username':'alice','key':'test','endpoint':'https://example.org'}
        HistorySync(self.store,session,backend).cycle()
        other=Store(Path(self.tmp.name)/'b.db');HistorySync(other,session,backend).cycle()
        self.assertIn('E50 = 5600',DocumentMemory(other).context('alice','tài liệu'))
        self.assertEqual(other.load(cid)['plaxis_active_problem'],state['plaxis_active_problem'])
    def test_ok_after_new_topic_does_not_restart_previous_task(self):
        state={'messages':[{'role':'assistant','content':PROPOSAL},{'role':'user','content':'ok'}]}
        confirmation_call('ok',state,True,True)
        state['messages'] += [{'role':'assistant','content':'Đã chạy xong.'},{'role':'user','content':'Hỏi về Word'},{'role':'assistant','content':'Thông tin Word.'},{'role':'user','content':'ok'}]
        self.assertIsNone(confirmation_call('ok',state,True,True))
    def test_failed_reads_are_not_recorded(self):
        self.memory.remember('alice',[{'file':'bad.pdf','text':'error','read_ok':False}])
        self.assertEqual(self.memory.records('alice'),[])
