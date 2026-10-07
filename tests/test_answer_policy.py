import json
import unittest
from assistant.answer_policy import evidence_record, select_examples, guard_answer, EXAMPLES
import test_app as fixtures
from assistant.agent import Agent

class PolicyTest(unittest.TestCase):
    def test_twenty_examples_bounded_and_matching_web_off(self):
        self.assertEqual(len(EXAMPLES),20)
        record=evidence_record({})
        examples=select_examples({'category':'current_web'},record)
        self.assertIn('web tắt',examples);self.assertLessEqual(len(examples),900)
        self.assertNotIn('Chào hỏi',examples)

    def test_snippet_partial_and_no_full_document_claim(self):
        state={'web_results':{'sources':[{'url':'https://x.test','title':'Title'}]}}
        self.assertEqual(evidence_record(state,True)['coverage'],'snippet')
        state['web_results']['pages']=[{'url':'https://x.test','text':'Text'}]
        self.assertEqual(evidence_record(state,True)['coverage'],'partial')
        safe,issues=guard_answer('Tôi đã đọc toàn văn tài liệu. Nội dung phần đã lấy là A.',state,True)
        self.assertIn('chưa xác nhận',safe);self.assertTrue(issues)

    def test_unsupported_test_and_file_claim_blocked_before_display(self):
        for text in ('Tôi đã kiểm thử thành công.','Tôi đã sửa file demo.py.'):
            safe,issues=guard_answer(text,{})
            self.assertNotEqual(safe,text);self.assertTrue(issues)
        state={'messages':[{'role':'user','content':'Sửa file'},
            {'role':'tool','tool_name':'file_edit','content':json.dumps({'ok':True})}]}
        text='Tôi đã sửa file demo.py.'
        self.assertEqual(guard_answer(text,state)[0],text)

    def test_old_tool_not_evidence_for_new_action(self):
        state={'messages':[{'role':'tool','tool_name':'file_edit','content':'{"ok":true}'},
            {'role':'user','content':'Sửa tiếp'}]}
        self.assertTrue(guard_answer('Tôi đã sửa file demo.py.',state)[1])

    def test_negation_quoted_text_code_translation_and_format_preserved(self):
        text='Chưa kiểm thử.\n\n```python\nprint("Tôi đã sửa file demo.py.")\n```\n'
        self.assertEqual(guard_answer(text,{})[0],text)
        text='Tôi đã kiểm thử thành công.'
        self.assertEqual(guard_answer(text,{},category='writing_translation')[0],text)
        self.assertEqual(guard_answer('Câu một. Câu hai.\n\nĐoạn ba.',{})[0],'Câu một. Câu hai.\n\nĐoạn ba.')

    def test_unknown_citation_does_not_override_retrieved_sources(self):
        state={'web_results':{'sources':[{'url':'https://real.test'}]}}
        text='[Nguồn A](https://real.test) và [Nguồn B](https://fake.test)'
        safe,issues=guard_answer(text,state,True)
        self.assertIn('https://real.test',safe);self.assertNotIn('https://fake.test',safe);self.assertTrue(issues)

class GuardIntegrationTest(unittest.TestCase):
    setUp=fixtures.AppTest.setUp
    tearDown=fixtures.AppTest.tearDown
    def test_stream_and_saved_reply_are_guarded_without_extra_model_calls(self):
        agent=Agent(fixtures.FakeClient([[fixtures.chunk('Tôi đã kiểm thử thành công.\n\n'),fixtures.chunk('Đây là hướng dẫn sử dụng.')]]),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Hướng dẫn lập trình Python','qwen2.5:7b')
        events=list(agent.run(state));visible=''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertNotIn('Tôi đã kiểm thử thành công',visible)
        self.assertIn('Chưa có kết quả',visible)
        self.assertIn('Đây là hướng dẫn',visible)
        self.assertTrue(state['answer_checks']['issues'])
        self.assertEqual(len(agent.client.requests),1)
