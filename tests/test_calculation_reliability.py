import json
import threading
import unittest
from copy import deepcopy
from unittest.mock import patch, Mock
from types import SimpleNamespace
import test_app as fixtures
from assistant.agent import Agent, bounded_context
from assistant.calculator import calculate
from assistant.calculation_response import calculation_answer
from assistant.cancellable_client import CancellableClient
from assistant.memory import PersonalMemory
from assistant.answer_policy import guard_answer


class CalculatorInputTests(unittest.TestCase):
    def test_ambiguous_group_requires_format(self):
        for expression in ('1.200*2','1,200*2','12.345+1'):
            with self.subTest(expression=expression),self.assertRaisesRegex(ValueError,'xác nhận'):
                calculate('expression',expression=expression)
        self.assertEqual(calculate('expression',expression='1.200*2',number_format='vi')['result'],'2400')
        self.assertEqual(calculate('expression',expression='1.200*2',number_format='canonical')['result'],'2.4')
        self.assertEqual(calculate('expression',expression='1,200*2',number_format='en')['result'],'2400')

    def test_unambiguous_formats_and_small_decimals(self):
        for expression,expected in [('1.234,56+1','1235.56'),('1,234.56+1','1235.56'),
                ('1.200.000*(1-15%)','1020000'),('2,5+0.125','2.625'),('1.234e2','123.4')]:
            with self.subTest(expression=expression):
                self.assertEqual(calculate('expression',expression=expression)['result'],expected)

    def test_original_user_input_is_checked_before_model_normalization(self):
        from assistant.calculator import ambiguous_input_question
        self.assertIn('1200',ambiguous_input_question('Tính 1.200 nhân hai'))
        self.assertIsNone(ambiguous_input_question('Tính 1.200 theo định dạng vi'))
        self.assertIsNone(ambiguous_input_question('Tính 1.234,56 cộng một'))

    def test_invalid_grouping_is_not_silently_reinterpreted(self):
        for expression in ('12.34,56','1,23,456','1.23.456'):
            with self.subTest(expression=expression),self.assertRaises(ValueError):
                calculate('expression',expression=expression)


class CalculationOutputTests(unittest.TestCase):
    setUp=fixtures.AppTest.setUp
    tearDown=fixtures.AppTest.tearDown

    def run_case(self,tool=True,review=False,conversation=False):
        class Client:
            def chat(inner,**kw):
                if kw.get('format'):
                    return {'message':{'content':json.dumps(dict(category='conversation' if conversation else 'calculation',
                        creative=False,complex=review,high_accuracy=False))}}
                if kw.get('stream') is False:return {'message':{'content':'Kết quả: 99999.'}}
                if not tool or kw['messages'][-1]['role']=='tool':return iter([fixtures.chunk('Kết quả: 99999.')])
                return iter([fixtures.chunk(calls=[fixtures.FakeCall('calculate',{'operation':'expression','expression':'3+4'})])])
        agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Tính 3+4','qwen2.5:7b')
        events=list(agent.run(state))
        return state,''.join(e.get('text','') for e in events if e['type']=='token')

    def test_wrong_model_answer_cannot_override_result(self):
        state,visible=self.run_case()
        self.assertIn('Kết quả: 7.',visible)
        self.assertNotIn('99999',visible)
        self.assertEqual(visible,state['messages'][-1]['content'])

    def test_review_cannot_reintroduce_uncomputed_answer(self):
        state,visible=self.run_case(tool=False,review=True)
        self.assertIn('Chưa nhận được kết quả',visible)
        self.assertNotIn('99999',visible)
        self.assertEqual(visible,state['messages'][-1]['content'])

    def test_ambiguous_question_does_not_reach_answer_model(self):
        client=Mock()
        agent=Agent(client,None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Tính 1.200*2','qwen2.5:7b')
        state['routing']={'category':'calculation'}
        events=list(agent.run(state))
        client.chat.assert_not_called()
        self.assertFalse(state['running'])
        self.assertIn('1200',state['messages'][-1]['content'])
        self.assertEqual(events[0]['text'],state['messages'][-1]['content'])

    def test_previous_turn_calculation_cannot_verify_new_turn(self):
        state={'messages':[{'role':'tool','tool_name':'calculate','content':json.dumps({'ok':True,'result':'7'})},
            {'role':'user','content':'Tính bài tiếp theo'}]}
        self.assertIn('Chưa nhận được kết quả',calculation_answer(state))

    def test_latest_input_survives_large_tool_result(self):
        latest='Dữ kiện cũ. '*100+'Dữ kiện cuối: x=42'
        messages=[{'role':'user','content':latest},{'role':'tool','content':'x'*18000}]
        before=deepcopy(messages)
        result=bounded_context(messages,3000)
        self.assertEqual(result[0]['content'],latest)
        self.assertEqual(messages,before)

    def test_oversized_latest_input_is_rejected_not_truncated(self):
        with self.assertRaisesRegex(ValueError,'chia nhỏ'):
            bounded_context([{'role':'user','content':'x'*6000+'LATEST=42'}],1800)

    def test_explicit_memory_persists_before_embedding_and_has_local_status(self):
        client=Mock()
        memory=PersonalMemory(self.store,client,'alice',True)
        ident=memory.capture_explicit('Ghi nhớ: tôi thích Python')
        self.assertTrue(ident)
        client.embed.assert_not_called()
        memory.put('tôi thích Python','Tiêu đề mới',ident)
        self.assertEqual(memory.list_local()[0]['title'],'Tiêu đề mới')
        value,_=guard_answer('Tôi đã lưu ghi nhớ lên server.',{'messages':[],'memory_write_status':'local_saved'})
        self.assertIn('chỉ được lưu trên máy',value)

    def test_conversation_classification_does_not_skip_explicit_memory(self):
        class Client:
            def chat(inner,**kw):
                if kw.get('format'):
                    return {'message':{'content':json.dumps(dict(category='conversation',creative=False,complex=False,high_accuracy=False))}}
                return iter([fixtures.chunk('Tôi đã lưu ghi nhớ lên server.')])
        agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        agent.memory=PersonalMemory(self.store,None,'alice')
        state=self.store.load(self.cid);agent.start(state,'Ghi nhớ: tôi thích Python','qwen2.5:7b')
        events=list(agent.run(state))
        self.assertEqual(state['memory_write_status'],'local_saved')
        self.assertTrue(agent.memory.search('Python'))
        visible=''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertNotIn('Tôi đã lưu ghi nhớ lên server.',visible)


class Cancelled(BaseException):pass


class LocalCancellationTests(unittest.TestCase):
    def test_blocked_nonstream_returns_on_cancel_without_late_result(self):
        started=threading.Event();release=threading.Event();cancel=threading.Event();finished=threading.Event()
        output=[]
        class Client:
            def chat(self,**kw):started.set();release.wait(2);return 'late result'
            def close(self):release.set()
        client=CancellableClient(Client(),cancel,Cancelled)
        def run():
            try:output.append(client.chat(stream=False))
            except Cancelled:output.append('cancelled')
            finally:finished.set()
        task=threading.Thread(target=run);task.start()
        try:
            self.assertTrue(started.wait(1));cancel.set()
            self.assertTrue(finished.wait(.6));self.assertEqual(output,['cancelled'])
        finally:release.set();task.join(2)

    def test_blocked_stream_is_closed_and_no_late_chunk_delivered(self):
        consumed=threading.Event();waiting=threading.Event();release=threading.Event();closed=threading.Event();cancel=threading.Event();done=threading.Event()
        output=[]
        class Client:
            def chat(self,**kw):
                try:
                    yield 'first';waiting.set();release.wait(2);yield 'late'
                finally:closed.set()
            def close(self):release.set()
        client=CancellableClient(Client(),cancel,Cancelled)
        def run():
            try:
                for value in client.chat(stream=True):
                    output.append(value);consumed.set()
            except Cancelled:output.append('cancelled')
            finally:done.set()
        task=threading.Thread(target=run);task.start()
        try:
            self.assertTrue(waiting.wait(1));self.assertTrue(consumed.wait(1));cancel.set()
            self.assertTrue(done.wait(.6));self.assertEqual(output,['first','cancelled'])
            self.assertTrue(closed.wait(1))
        finally:release.set();task.join(2)

    def test_transport_exception_is_preserved(self):
        def fail(**kw):raise ValueError('fixture network error')
        client=CancellableClient(SimpleNamespace(chat=fail),threading.Event(),Cancelled)
        with self.assertRaisesRegex(ValueError,'fixture network error'):client.chat(stream=False)
