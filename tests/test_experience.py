import json
import unittest
from assistant.experience import CARDS, select_cards, task_record, repeated_failure
from assistant.answer_policy import evidence_record
import test_app as fixtures
from assistant.agent import Agent


def pair(error='offline',denied=False,args=None):
    return [{'role':'assistant','content':'','tool_calls':[{'function':{'name':'web_read','arguments':args or {'url':'https://example.test'}}}]},
        {'role':'tool','tool_name':'web_read','content':json.dumps({'ok':False,'error':error,'denied':denied})}]

class ExperienceTest(unittest.TestCase):
    def test_cards_count_selection_and_budget(self):
        self.assertEqual(len(CARDS),32)
        chosen=select_cards('Ứng dụng khởi động rồi tự tắt',{'category':'coding'},evidence_record({}))
        self.assertEqual(chosen,[])  # No canned experience instructions are injected.
        self.assertEqual(select_cards('Xin chào',{'category':'conversation'},evidence_record({})),[])

    def test_discussion_does_not_mean_permission_or_claim_success(self):
        state={'messages':[{'role':'user','content':'Hãy đề xuất trước, chưa sửa'}, {'role':'assistant','content':'Tôi đã sửa file'}]}
        record=task_record(state)
        self.assertEqual(record['phase'],'discussion');self.assertEqual(record['attempts'],[])

    def test_identical_failure_blocked_changed_args_or_new_turn_allowed(self):
        state={'messages':[{'role':'user','content':'Tra mạng'}]+pair()+pair()}
        call={'function':{'name':'web_read','arguments':{'url':'https://example.test'}}}
        self.assertTrue(repeated_failure(state,call))
        other={'function':{'name':'web_read','arguments':{'url':'https://other.test'}}}
        self.assertIsNone(repeated_failure(state,other))
        state['messages'].append({'role':'user','content':'Tôi đã sửa mạng, hãy thử lại'})
        self.assertIsNone(repeated_failure(state,call))

    def test_denial_blocks_repeat_and_error_secrets_are_redacted(self):
        state={'messages':[{'role':'user','content':'Tra mạng'}]+pair('token=secret-value',True)}
        self.assertTrue(repeated_failure(state,{'function':{'name':'web_read','arguments':{'url':'https://example.test'}}}))
        self.assertNotIn('secret-value',json.dumps(task_record(state)))

class ExperienceIntegrationTest(unittest.TestCase):
    setUp=fixtures.AppTest.setUp
    tearDown=fixtures.AppTest.tearDown
    def test_natural_reply_has_no_cards_and_keeps_progress(self):
        client=fixtures.FakeClient([[fixtures.chunk('Hãy gửi lỗi cuối trong startup.log.')]])
        agent=Agent(client,None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Ứng dụng tự tắt khi khởi động','qwen2.5:7b')
        list(agent.run(state))
        saved=self.store.load(self.cid)
        self.assertEqual(saved['experience_cards'],[])
        self.assertEqual(saved['task_progress']['attempts'],[])
        self.assertEqual(len(client.requests),1)
        self.assertNotIn('startup:',client.requests[0]['messages'][0]['content'])

    def test_identical_failed_tool_executes_only_twice(self):
        from unittest.mock import patch
        calls=[fixtures.chunk(calls=[fixtures.FakeCall('excel_list_files',{})])]
        client=fixtures.FakeClient([calls,calls,calls,[fixtures.chunk('Chưa đọc được; cần kiểm tra thư mục.')]])
        agent=Agent(client,self.excel,self.cfg,self.store,self.cid)
        state=self.store.load(self.cid);agent.start(state,'Liệt kê file','qwen2.5:7b')
        with patch.object(self.excel,'excel_list_files',side_effect=OSError('offline')) as tool:
            list(agent.run(state));self.assertEqual(tool.call_count,2)
        self.assertTrue(any('hai lần' in m['content'] for m in state['messages'] if m['role']=='tool'))

    def test_discussion_blocks_write_before_preview(self):
        calls=[fixtures.chunk(calls=[fixtures.FakeCall('excel_edit_cell',{'path':'demo.xlsx','sheet':'Data','cell':'B2','value':99})])]
        agent=Agent(fixtures.FakeClient([calls,[fixtures.chunk('Đây là đề xuất.')]]),self.excel,self.cfg,self.store,self.cid)
        state=self.store.load(self.cid);agent.start(state,'Chỉ đề xuất trước, chưa sửa file','qwen2.5:7b')
        list(agent.run(state))
        self.assertIsNone(state['pending'])
        self.assertTrue(any('trao đổi/đề xuất' in m['content'] for m in state['messages'] if m['role']=='tool'))
