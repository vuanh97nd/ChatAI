import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from assistant.procedure_memory import ProcedureMemory,user_instruction
from assistant.storage import Store


class UserProcedureMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        # Use a temporary database directly, without creating LocalAppData fixtures.
        self.store=Store.__new__(Store);self.store.path=str(Path(self.tmp.name)/'memory.db')
        with self.store.connection() as db:
            db.executescript('CREATE TABLE procedure_memory(owner TEXT,id TEXT,data TEXT,updated TEXT,PRIMARY KEY(owner,id));'
                             'CREATE TABLE procedure_accounts(owner TEXT PRIMARY KEY,server TEXT);')
        self.memory=ProcedureMemory(self.store)
        self.text='Quy trình Excel: chọn sheet Data, điền số lượng vào cột B, giữ nguyên công thức cột D. Lần sau hãy làm theo cách này.'
        self.state={'messages':[{'role':'user','content':self.text}],'procedure_memory_version':1}

    def test_instruction_is_recalled_after_restart_in_another_chat(self):
        self.memory.seed('alice',self.state)
        reopened=Store.__new__(Store);reopened.path=self.store.path
        context=ProcedureMemory(reopened).context('alice','Điền số lượng Excel')
        self.assertIn('giữ nguyên công thức cột D',context)
        self.assertIn('không yêu cầu dạy lại',context)
        self.assertEqual(ProcedureMemory(reopened).context('bob','Excel'),'')
        self.assertEqual(ProcedureMemory(reopened).context('alice','Thời tiết Hà Nội'),'')

    def test_repeated_saves_do_not_duplicate_or_refresh_instruction(self):
        self.memory.seed('alice',self.state);before=self.memory.records('alice')
        self.memory.seed('alice',self.state)
        self.memory.seed('alice',dict(self.state,last_user_instruction_id=''))
        self.assertEqual(self.memory.records('alice'),before)

    def test_only_user_teaching_is_captured_not_ai_claims_or_regular_tasks(self):
        self.assertEqual(user_instruction('Hãy đọc file Excel và báo số lượng của mặt hàng A.'),'')
        self.assertEqual(user_instruction('Đừng ghi nhớ quy trình Excel: chọn sheet Data và sửa B2.'),'')
        self.assertFalse(self.memory.capture_instruction('alice',{'messages':[{'role':'assistant','content':self.text}]}))
        self.assertTrue(user_instruction('Trong Excel:\n1. Chọn sheet Data.\n2. Điền số lượng vào cột B.'))

    def test_secret_is_redacted_and_instruction_is_not_executable(self):
        self.state['messages'][0]['content']=self.text+' token=private-value'
        self.memory.seed('alice',self.state)
        record=self.memory.records('alice')[0]
        self.assertNotIn('private-value',json.dumps(record))
        self.assertFalse(record['training'])
        self.assertNotIn('pending',self.state);self.assertNotIn('queue',self.state)
        self.assertIn('chưa xác minh',record['evidence'])

    def test_normal_conversation_save_captures_teaching_without_migration(self):
        with patch.dict(os.environ,{'LOCALAPPDATA':''}):
            store=Store(Path(self.tmp.name)/'history.db')
        cid=store.create(False)
        state=store.load(cid)
        state.update(account_username='alice',procedure_memory_version=1,
                     messages=[{'role':'user','content':self.text}])
        store.save(cid,state)
        restored=store.load(cid)
        self.assertEqual(len(restored['procedure_memory']),1)
        self.assertEqual(restored['procedure_memory'][0]['tool'],'user_instruction')
        self.assertIn('giữ nguyên công thức',ProcedureMemory(store).context('alice','Excel số lượng'))
        self.assertFalse(restored['running']);self.assertIsNone(restored['pending'])


if __name__=='__main__':unittest.main()
