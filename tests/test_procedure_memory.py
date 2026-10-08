import json
import tempfile
import unittest
from pathlib import Path

from assistant.procedure_memory import ProcedureMemory
from assistant.storage import Store
from assistant.history_sync import HistorySync
from test_history_sync import Backend


class ProcedureMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'a.db');self.memory=ProcedureMemory(self.store)
        self.state={'account_username':'alice','messages':[{'role':'user','content':'Viết đơn Word font Times New Roman 13'}],
                    'running':False,'pending':None,'queue':[]}
        self.call={'function':{'name':'word_create_open','arguments':{'font_name':'Times New Roman','font_size':'13'}}}

    def test_success_recalled_after_restart_but_not_for_another_topic_or_owner(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'document_created':True})
        memory=ProcedureMemory(Store(self.store.path))
        self.assertIn('Times New Roman',memory.context('alice','Viết đơn Word'))
        self.assertEqual(memory.context('bob','Viết đơn Word'),'')
        self.assertEqual(memory.context('alice','thời tiết Hà Nội'),'')

    def test_old_tool_history_is_migrated_once_without_trusting_assistant_claims(self):
        cid=self.store.create(False)
        self.state['messages'] += [{'role':'assistant','content':'','tool_calls':[self.call]},
            {'role':'tool','tool_name':'word_create_open','content':'{"ok":true,"document_created":true}'},
            {'role':'assistant','content':'Đã chạy PLAXIS thành công.'}]
        self.store.save(cid,self.state)
        first=self.memory.export('alice')
        self.store.save(cid,self.store.load(cid))
        self.assertEqual(self.memory.export('alice'),first)
        self.assertEqual(first[0]['tool'],'word_create_open')

    def test_failure_is_not_promoted_to_success_and_unverified_claim_is_not_saved(self):
        self.memory.remember('alice',self.state,self.call,{'ok':False,'error':'Font không hỗ trợ'})
        self.memory.remember('alice',self.state,self.call,{'note':'AI nói đã xong'})
        self.memory.remember('alice',self.state,self.call,{'ok':True,'uncertain':True})
        self.memory.remember('alice',self.state,self.call,{'ok':False,'denied':True})
        self.assertEqual(len(self.memory.records('alice')),1)
        self.assertEqual(self.memory.records('alice')[0]['outcome'],'failed')

    def test_credentials_and_ui_handles_are_removed_without_changing_false(self):
        call={'function':{'name':'plaxis_generate_script','arguments':{'auto_run':False,'session':'private-session',
              'problem':json.dumps({'height':4,'api_key':'private-key'}),'password':'private-password'}}}
        self.memory.remember('alice',self.state,call,{'ok':True})
        record=self.memory.export('alice')[0]
        self.assertNotIn('private-',json.dumps(record))
        self.assertIs(json.loads(record['arguments'])['auto_run'],False)

    def test_cloud_restore_makes_procedure_available_in_a_new_conversation_without_execution(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'document_created':True})
        cid=self.store.create(False);self.store.save(cid,self.state)
        backend=Backend();session={'username':'alice','key':'test','endpoint':'https://example.org'}
        HistorySync(self.store,session,backend).cycle()
        other=Store(Path(self.tmp.name)/'b.db');HistorySync(other,session,backend).cycle()
        self.assertIn('Times New Roman',ProcedureMemory(other).context('alice','Viết đơn Word'))
        restored=other.load(cid)
        self.assertFalse(restored['running']);self.assertEqual(restored['queue'],[])
        self.assertIsNone(restored['pending'])
