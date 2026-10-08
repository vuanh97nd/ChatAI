"""A blocked network/preparation call must not hide the locally accepted prompt."""
import copy,tempfile,unittest
from pathlib import Path
from threading import Event,Thread
from types import SimpleNamespace
from unittest.mock import Mock,patch
from assistant.support_ui import SupportMixin
from assistant.storage import Store
from assistant.cloud import CloudError

class OnlineSendVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        store=Store(Path(self.temp.name)/'history.db');cid=store.create()
        self.view=SimpleNamespace(busy=lambda:False,store=store,cid=cid,server_session={'endpoint':'https://example.com','username':'admin','key':'test-session'},model=Mock(),cfg={},chat_mode=Mock(),pending_documents=[],pending_image=None,answer_actions=Mock(),reply_dots=Mock(),reply_timer=Mock(),status=Mock(),worker=SimpleNamespace(stop_requested=Event()),manager=Mock())
        self.view.model.currentText.return_value='DeepSeek API';self.view.chat_mode.currentIndex.return_value=0;self.view.manager.ready.return_value=False
        self.view.work=lambda task,done,**kwargs:setattr(self.view,'task',task)
    def start(self,prompt):SupportMixin.cloud_chat_task(self.view,prompt)
    def assert_visible(self,events,prompt):
        state=self.view.store.load(self.view.cid)
        self.assertEqual(state['messages'][-1],{'role':'user','content':prompt})
        self.assertTrue(state['running'])
        self.assertEqual([e['type'] for e in events[:2]],['sent','snapshot'])
        self.assertEqual(events[1]['messages'][-1]['content'],prompt)
    def test_snapshot_precedes_first_remote_event_and_history_does_not_duplicate_prompt(self):
        for name,hook in [('DeepSeek API','api_answer_events'),('Cloudflare AI','cloud_events')]:
            with self.subTest(name=name):
                self.view.cid=self.view.store.create();self.view.model.currentText.return_value=name
                events=[];blocked=Event();release=Event();result={};bodies=[]
                def answers(client,body):
                    bodies.append(body);blocked.set();release.wait(2)
                    yield 'meta',{}
                    yield 'delta',{'text':'OK'}
                    yield 'done',{}
                def run():
                    try:result['value']=self.view.task(lambda event:events.append(copy.deepcopy(event)))
                    except Exception as error:result['error']=error
                with patch('assistant.support_ui.'+hook,answers):
                    self.start('Xin chào');thread=Thread(target=run);thread.start()
                    try:
                        self.assertTrue(blocked.wait(1));self.assert_visible(events,'Xin chào')
                        self.assertEqual(bodies[0]['history'],[])
                    finally:release.set();thread.join(2)
                self.assertFalse(thread.is_alive());self.assertNotIn('error',result)
                self.assertIn('chờ chữ đầu tiên',result['value']['message'])
                self.assertEqual(set(result['value']['timing']),{'preparation','first_text_wait','answer_receiving'})
                self.assertTrue(all(n>=0 for n in result['value']['timing'].values()))
                state=self.view.store.load(self.view.cid)
                self.assertEqual([m['content'] for m in state['messages']],['Xin chào','OK'])
                self.assertFalse(state['running'])
    def test_document_preparation_failure_preserves_user_prompt_and_clears_running(self):
        self.view.manager.ready.return_value=True
        events=[]
        def fail(*args,**kwargs):
            self.assert_visible(events,'Đọc tài liệu');raise CloudError('Network failure')
        with patch('assistant.document_intent.analyze_intent',side_effect=fail):
            self.start('Đọc tài liệu')
            with self.assertRaisesRegex(CloudError,'Network failure'):self.view.task(lambda event:events.append(copy.deepcopy(event)))
        state=self.view.store.load(self.view.cid)
        self.assertFalse(state['running']);self.assertEqual(len(state['messages']),1)
    def test_quota_failure_preserves_prompt(self):
        events=[]
        def fail(*args):
            self.assert_visible(events,'Xin chào');raise CloudError('Unavailable','CLOUD_BUSY');yield
        with patch('assistant.support_ui.api_answer_events',fail):
            self.start('Xin chào');result=self.view.task(lambda event:events.append(copy.deepcopy(event)))
        self.assertEqual(result['cloud_action'],'CLOUD_BUSY')
        self.assertFalse(self.view.store.load(self.view.cid)['running'])
        self.assertEqual(len(self.view.store.load(self.view.cid)['messages']),1)

    def test_document_word_without_sources_skips_extra_intent_api_call(self):
        seen=[]
        def answer(client,body):
            seen.append(body)
            yield 'meta',{}
            yield 'delta',{'text':'OK'}
            yield 'done',{}
        with patch('assistant.document_intent.analyze_intent',side_effect=AssertionError('Unneeded intent call')),patch('assistant.support_ui.api_answer_events',answer):
            self.start('Viết báo cáo giải thích số liệu')
            self.view.task(lambda event:None)
        self.assertEqual(len(seen),1)
        self.assertTrue(seen[0]['document_sources_unavailable'])
        self.assertFalse(self.view.store.load(self.view.cid)['running'])

    def test_online_options_do_not_inherit_local_limits(self):
        self.view.cfg={'num_predict':768,'temperature':.9,'num_ctx':2048,'api_num_predict':3072,'api_temperature':.1}
        bodies=[]
        def answer(client,body):
            bodies.append(body)
            yield 'meta',{}
            yield 'delta',{'text':'OK'}
            yield 'done',{}
        with patch('assistant.support_ui.api_answer_events',answer):
            self.start('Xin chào');self.view.task(lambda event:None)
        self.assertEqual(bodies[0]['options'],{'num_predict':3072,'temperature':.1})
        self.assertEqual(bodies[0]['max_tokens'],3072)
