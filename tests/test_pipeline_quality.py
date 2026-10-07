import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_app as fixtures
from assistant.agent import Agent
from assistant.feedback import FeedbackStore
from assistant.memory import PersonalMemory
from assistant.rag import RagTools
from assistant.files import FileTools
from assistant.excel import digest
from assistant.quality import followups

class PipelineQualityTest(unittest.TestCase):
    setUp=fixtures.AppTest.setUp
    tearDown=fixtures.AppTest.tearDown

    def test_fast_chat_calculator_tool_round_trip(self):
        class Client:
            def chat(self,**kwargs):
                if kwargs.get('stream') is False:
                    return {'message':{'content':json.dumps(dict(category='calculation',creative=False,complex=False,high_accuracy=False))}}
                if kwargs['messages'][-1]['role']=='tool':
                    result=json.loads(kwargs['messages'][-1]['content'])
                    assert result['ok'] and result['result']=='0.3',result
                    return iter([fixtures.chunk('Kết quả: 0,3.')])
                return iter([fixtures.chunk(calls=[fixtures.FakeCall('calculate',{'operation':'expression','expression':'0.1+0.2'})])])
        agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Tính 0.1+0.2','qwen2.5:7b')
        events=list(agent.run(state))
        self.assertFalse(state['running']);self.assertIsNone(state['pending'])
        self.assertEqual(state['messages'][-1]['content'],'Kết quả: 0,3.')
        self.assertTrue(any('Đang tính bằng Python' in e.get('text','') for e in events))

    def test_complex_review_hides_draft_and_only_emits_checked_answer(self):
        calls=[]
        class Client:
            def chat(self,**kwargs):
                calls.append(kwargs)
                if kwargs.get('format'):
                    return {'message':{'content':json.dumps(dict(category='knowledge',creative=False,complex=True,high_accuracy=False))}}
                if kwargs.get('stream') is False:return {'message':{'content':'Bản đã rà soát'}}
                return iter([fixtures.chunk('Bản nháp không được hiện')])
        agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Phân tích kế hoạch này','qwen2.5:7b')
        events=list(agent.run(state))
        text=''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertEqual(text,'Bản đã rà soát');self.assertEqual(len(calls),3)
        self.assertEqual(state['review_status'],'completed')
        self.assertEqual(len(state['followups']),3)

    def test_review_failure_keeps_answer_and_flags_limit(self):
        class Client:
            def chat(self,**kwargs):
                if kwargs.get('format'):return {'message':{'content':json.dumps(dict(category='knowledge',creative=False,complex=False,high_accuracy=True))}}
                if kwargs.get('stream') is False:raise TimeoutError('offline')
                return iter([fixtures.chunk('Câu trả lời có căn cứ')])
        agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Một câu hỏi y tế','qwen2.5:7b')
        list(agent.run(state));self.assertEqual(state['review_status'],'failed')
        self.assertIn('chưa hoàn tất',state['messages'][-1]['content'])

    def test_explicit_web_prepares_once_and_full_sources(self):
        class Client:
            def chat(self,**kwargs):
                if kwargs.get('format'):return {'message':{'content':json.dumps(dict(category='current_web',creative=False,complex=False,high_accuracy=False))}}
                return iter([fixtures.chunk('Thông tin mới [S1]')])
        research={'sources':[{'id':'S1','url':'https://example.org/news','title':'Tin mới'}],'pages':[]}
        with patch('assistant.web.WebTools.research_events',return_value=iter([{'type':'research_result','result':research}])) as search:
            agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
            state=self.store.load(self.cid);agent.start(state,'Tìm tin mới','qwen2.5:7b')
            state.update(ui_mode=4,web_search_requested=True)
            list(agent.run(state))
            self.assertEqual(search.call_count,1)
            self.assertIn('example.org - Tin mới - https://example.org/news',state['messages'][-1]['content'])

    def test_feedback_owner_and_negative_snapshot(self):
        state=self.store.load(self.cid);state['account_username']='alice';state['model']='qwen2.5:7b'
        state['messages']=[{'role':'user','content':'Câu hỏi'},{'role':'assistant','content':'Câu trả lời'}]
        self.store.save(self.cid,state);feedback=FeedbackStore(self.store)
        with self.assertRaises(PermissionError):feedback.put('bob',self.cid,1,-1)
        feedback.put('alice',self.cid,1,-1,'Thiếu ví dụ')
        self.assertEqual(feedback.poor_answers('bob'),[])
        self.assertEqual(feedback.poor_answers('alice')[0]['comment'],'Thiếu ví dụ')
        self.assertEqual(feedback.poor_answers('alice')[0]['answer'],'Câu trả lời')

    def test_rag_owner_isolation_and_changed_file_rejected(self):
        source=self.allowed/'note.txt';source.write_text('Kiến thức Python')
        files=FileTools([self.allowed],self.root/'backups',lambda *args:None)
        a=RagTools(files,None,self.root,lambda *args:None,owner='alice')
        b=RagTools(files,None,self.root,lambda *args:None,owner='bob')
        self.assertNotEqual(a.collection_name,b.collection_name)
        before=digest(source)
        coll=SimpleNamespace(count=lambda:1,query=lambda **kwargs:{'documents':[['Kiến thức Python']],
            'metadatas':[[{'source':str(source),'sha256':before,'chunk':1}]],'distances':[[.1]]})
        a.collection=lambda:coll;a.embed=lambda *args,**kwargs:[[1.,0.]]
        self.assertEqual(len(a.rag_search('Python')['sources']),1)
        source.write_text('Đã thay đổi')
        self.assertEqual(a.rag_search('Python')['sources'],[])

    def test_semantic_memory_batches_and_persists_vectors(self):
        class Client:
            def embed(self,**kwargs):
                self.last=kwargs
                return {'embeddings':[[1.,0.] for _ in kwargs['input']]}
        client=Client();memory=PersonalMemory(self.store,client,'alice',True)
        memory.sync_server([{'id':'1','text':'Tôi thích lập trình','title':'Sở thích'}])
        hits=memory.search('software engineering')
        self.assertEqual(len(hits),1);self.assertEqual(client.last['options']['num_gpu'],0)
        self.assertEqual(len(client.last['input']),2)
        self.assertEqual(PersonalMemory(self.store,client,'bob',True).search('software'),[])

    def test_followups_are_bounded_and_category_appropriate(self):
        self.assertEqual(followups('conversation','Xin chào'),[])
        self.assertEqual(len(followups('coding','def main(): pass')),3)
        self.assertIn('kiểm thử',followups('coding','code')[0]['prompt'])

    def test_history_titles_are_filtered_by_account(self):
        state=self.store.load(self.cid);state['account_username']='alice'
        state['messages']=[{'role':'user','content':'Private question'}];self.store.save(self.cid,state)
        self.assertEqual(self.store.list('bob'),[])
        self.assertEqual(self.store.list(''),[])
        self.assertEqual(self.store.list('alice'),[(self.cid,'Private question')])

    def test_calculator_statistics_schema_allows_numeric_array(self):
        from assistant.tools import validate_call
        from assistant.calculator import CALCULATOR_SCHEMA
        validate_call('calculate',{'operation':'statistics','values':[1,2,8,9]},[CALCULATOR_SCHEMA])
        with self.assertRaises(ValueError):validate_call('calculate',{'operation':'statistics','values':['1']},[CALCULATOR_SCHEMA])

    def test_no_calculator_result_no_unverified_numeric_answer(self):
        class Client:
            def chat(self,**kwargs):
                if kwargs.get('format'):return {'message':{'content':json.dumps(dict(category='calculation',creative=False,complex=False,high_accuracy=False))}}
                return iter([fixtures.chunk('Kết quả là 99999.')])
        agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Tính 3+4','qwen2.5:7b')
        events=list(agent.run(state))
        visible=''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertNotIn('99999',visible);self.assertIn('Chưa nhận được kết quả',visible)

    def test_context_compaction_does_not_mutate_saved_data(self):
        from copy import deepcopy
        from assistant.context import compact_evidence
        state={'attached_documents':[{'name':'test.txt','text':'ABC '*4000}]}
        original=deepcopy(state)
        result=compact_evidence(state,budget=1500)
        self.assertEqual(state,original)
        self.assertLess(len(json.dumps(result,ensure_ascii=False)),1800)

    def test_benchmark_thirty_unique_cases(self):
        path=Path(__file__).resolve().parents[1]/'evaluation/questions.json'
        cases=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(cases),30);self.assertEqual(len({q['id'] for q in cases}),30)
        self.assertTrue(all(q['criteria'] and q['question'] for q in cases))

    def test_current_question_does_not_search_with_button_off(self):
        class Client:
            def chat(self,**kwargs):
                if kwargs.get('format'):return {'message':{'content':json.dumps(dict(category='current_web',creative=False,complex=False,high_accuracy=False))}}
                return iter([fixtures.chunk('Hãy bật Tìm kiếm mạng để tra tin hiện tại.')])
        with patch('assistant.web.WebTools.research_events',side_effect=AssertionError('must not search')) as search:
            agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
            state=self.store.load(self.cid);agent.start(state,'Tin tức hôm nay','qwen2.5:7b')
            list(agent.run(state))
            search.assert_not_called()
            self.assertIsNone(state['web_results'])

    def test_web_tools_are_removed_and_rogue_call_blocked(self):
        from assistant.tools import schema,TEXT
        client=fixtures.FakeClient([[fixtures.chunk(calls=[fixtures.FakeCall('web_read',{'url':'https://example.com'})])],[fixtures.chunk('Công cụ mạng chưa được bật.')]])
        agent=Agent(client,self.excel,self.cfg,self.store,self.cid)
        agent.schemas.extend([schema('web_read','read',{'url':TEXT},['url']),schema('python_search','search',{'code':TEXT},['code'])])
        state=self.store.load(self.cid);agent.start(state,'Giải thích vấn đề này','qwen2.5:7b')
        list(agent.run(state))
        self.assertFalse(any(t['function']['name'] in ('web_read','python_search') for t in client.requests[0]['tools']))
        result=json.loads(next(m['content'] for m in state['messages'] if m['role']=='tool'))
        self.assertFalse(result['ok']);self.assertIn('registry',result['error'])

    def test_legacy_mode_four_without_explicit_permission_is_denied(self):
        agent=Agent(None,None,self.cfg,self.store,self.cid,tools_enabled=False)
        self.assertFalse(agent.web_allowed({'ui_mode':4}))
        self.assertFalse(agent.web_allowed({'ui_mode':0,'web_search_requested':True}))
        self.assertTrue(agent.web_allowed({'ui_mode':4,'web_search_requested':True}))
