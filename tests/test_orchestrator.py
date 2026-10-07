"""Kiểm tra điều phối bằng SDK giả: không đo chất lượng OCR/model thật."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from assistant.orchestrator import Orchestrator, SerialClient, load_experts, validate_observation
from assistant.agent import Agent
from assistant.storage import Store
from assistant.tools import EXTRA_TOOLS
import test_app as fixtures

OBS={'kind':'code','description':'Ảnh code Python','text':'print(1)','code_blocks':[
    {'language':'python','code':'print(1)','filename':'main.py'}],'errors':[], 'tables':[], 'uncertain':[]}
CFG={'roots':[],'num_ctx':4096,'num_predict':1000,'max_rounds':8,'code_model':'qwen2.5-coder:7b'}

class Client:
    def __init__(self,observation=None,vision_error=False):
        self.requests=[];self.unloads=[];self.observation=observation or OBS;self.vision_error=vision_error
    def list(self):return {'models':[{'model':x} for x in ['qwen2.5:3b','qwen2.5:7b','qwen2.5-coder:7b','gemma3:4b']]}
    def ps(self):return {'models':[]}
    def generate(self,**kw):self.unloads.append(kw);return {}
    def chat(self,**kw):
        self.requests.append(kw)
        if kw.get('format'):
            keys=kw['format']['properties']
            if 'kind' in keys:
                if self.vision_error:raise TimeoutError('fake')
                return {'message':{'content':json.dumps(self.observation)},'load_duration':1000000000}
            if 'prompts' in keys:return {'message':{'content':json.dumps({'prompts':['a robot logo'],'assumptions':[]})}}
            return {'message':{'content':json.dumps({'category':'coding','creative':False,'complex':False,'high_accuracy':False})}}
        if kw.get('stream') is False:return {'message':{'content':'a robot logo'}}
        return iter([fixtures.chunk('Đây là code đã sửa:\n```python\nprint(1)\n```\nChưa chạy thử.')])

class OrchestratorTest(unittest.TestCase):
    def state(self,question='Sửa code trong ảnh',image=True,files=False,web=False):
        message={'role':'user','content':question}
        if image:message['images']=['data']
        return {'model':'qwen2.5:7b','messages':[message],'ui_mode':5,'web_search_requested':web,
                'attached_documents':[{'file':'demo.txt'}] if files else [],'expert_override':None}
    def route(self,category='knowledge',**team):return {'category':category,'team':team}
    def test_twenty_coordination_plans(self):
        cases=json.loads((Path(__file__).with_name('orchestrator_cases.json')).read_text())
        self.assertEqual(len(cases),20)
        for case in cases:
            with self.subTest(case=case['id']):
                o=Orchestrator(Client(),CFG);state=self.state(case['question'],case['image'],case['files'],case['web'])
                o.prepare(state,self.route(case['category'],need_code=case.get('need_code',False),need_rag=case.get('rag',False)))
                roles={x['expert'] for x in state['orchestration']['plan']['steps']}
                self.assertTrue(set(case['roles'])<=roles)
                self.assertEqual(state['orchestration']['plan']['need_web'],case['web'])
                self.assertEqual(state['orchestration']['original_question'],case['question'])
    def test_structured_vision_to_coder_preserves_code(self):
        client=Client();o=Orchestrator(client,CFG);state=self.state();o.prepare(state,self.route())
        events=list(o.vision_events(state));instruction=o.instruction(state)
        self.assertEqual(o.final_expert(state)[0],'qwen2.5-coder:7b')
        self.assertIn('main.py',instruction);self.assertIn('print(1)',instruction)
        self.assertFalse(state['orchestration']['results']['vision']['verified'])
        self.assertIn('Đang đọc ảnh',events[0]['text'])
    def test_failed_vision_no_invented_observation(self):
        o=Orchestrator(Client(vision_error=True),CFG);state=self.state();o.prepare(state,self.route())
        list(o.vision_events(state));result=state['orchestration']['results']['vision']
        self.assertFalse(result['ok']);self.assertNotIn('observation',result)
        answer=o.finish(state,'Có thể hướng dẫn phần code bạn gửi bằng chữ.')
        self.assertIn('Chưa đọc được ảnh',answer)
    def test_invalid_nested_ocr_rejected(self):
        with self.assertRaises(ValueError):validate_observation({**OBS,'code_blocks':[{'code':123}]})
        with self.assertRaises(ValueError):validate_observation({**OBS,'tables':[{'headers':[],'rows':[['A',42]]}]})
    def test_same_model_not_reloaded_and_switch_unloads(self):
        raw=Client();client=SerialClient(raw)
        list(client.chat(model='qwen2.5:7b',stream=True));list(client.chat(model='qwen2.5:7b',stream=True))
        self.assertEqual(raw.unloads,[])
        list(client.chat(model='qwen2.5-coder:7b',stream=True))
        self.assertEqual(raw.unloads[0]['model'],'qwen2.5:7b');self.assertEqual(raw.unloads[0]['keep_alive'],0)
        self.assertEqual(len(client.metrics),3)
    def test_memory_retained_after_finish(self):
        o=Orchestrator(Client(),CFG);state=self.state(image=False);o.prepare(state,self.route())
        o.sync(state,[{'text':'Người dùng thích ví dụ ngắn.'}]);o.finish(state,'Kết quả.')
        self.assertEqual(state['orchestration']['memory'][0]['text'],'Người dùng thích ví dụ ngắn.')
    def test_web_permission_never_granted_by_plan(self):
        o=Orchestrator(Client(),CFG);state=self.state(image=False);o.prepare(state,self.route(need_web=True))
        self.assertFalse(state['orchestration']['plan']['need_web'])
    def test_unfinished_media_reported_not_claimed(self):
        o=Orchestrator(Client(),CFG);state=self.state('Tạo ảnh logo',False);o.prepare(state,self.route())
        list(o.pre_answer_events(state));answer=o.finish(state,'Mô tả logo.')
        self.assertIn('Chưa tạo được ảnh',answer)
        self.assertEqual(state['orchestration']['results']['prompt']['prompts'],['a robot logo'])
    def test_uncertain_image_never_auto_sandbox(self):
        o=Orchestrator(Client(),CFG);state=self.state();o.prepare(state,self.route('coding'))
        schemas=[s for m,s in EXTRA_TOOLS if s['function']['name']=='python_run']
        self.assertIsNone(o.sandbox_call(state,'```python\n[KHÔNG ĐỌC RÕ]\n```',schemas))
        call=o.sandbox_call(state,'```python\nprint(1)\n```',schemas)
        self.assertEqual(call['function']['arguments']['code'],'print(1)')
        state['messages'][0]['content']='Không chạy code';state['orchestration']['original_question']='Không chạy code'
        self.assertIsNone(o.sandbox_call(state,'```python\nprint(1)\n```',schemas))
    def test_registry_reload_and_custom_expert(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'experts.yaml';path.write_text(json.dumps({'experts':[{'name':'editor','kind':'llm','role':'editing','model':'qwen2.5:7b','when':{'need_code':True}}]}))
            cfg=load_experts(path)
            with patch('assistant.orchestrator.load_experts',return_value=cfg):
                o=Orchestrator(Client(),CFG);state=self.state(image=False);o.prepare(state,self.route('coding'))
                self.assertIn('editor',[x['expert'] for x in state['orchestration']['plan']['steps']])
            path.write_text('invalid: [');self.assertIn('error',load_experts(path))
    def test_agent_expert_vision_to_code_single_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'history.db');cid=store.create();state=store.load(cid);client=Client()
            agent=Agent(client,None,CFG,store,cid,tools_enabled=False)
            # PNG signature is sufficient for start(); OCR bytes are never really processed by this fake.
            agent.start(state,'Sửa code trong ảnh','qwen2.5:7b',images=[base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()],expert_mode=True)
            state['ui_mode']=5
            events=list(agent.run(state));tokens=[x['text'] for x in events if x['type']=='token']
            self.assertEqual(len(tokens),1);self.assertIn('print(1)',tokens[0])
            calls=[x for x in client.requests if x.get('stream')]
            self.assertEqual(calls[-1]['model'],'qwen2.5-coder:7b')
            self.assertIn('main.py',calls[-1]['messages'][0]['content'])
            self.assertFalse(any(m.get('images') for m in calls[-1]['messages']))
            self.assertFalse(state['running']);self.assertFalse(state['orchestration']['coverage']['semantic_verified'])
    def test_agent_expert_web_off_cannot_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'history.db');cid=store.create();state=store.load(cid)
            agent=Agent(Client(),None,CFG,store,cid,tools_enabled=False)
            agent.start(state,'Viết code Python','qwen2.5:7b',expert_mode=True);state['ui_mode']=5
            with patch('assistant.web.WebTools.research_events',side_effect=AssertionError('Web bị tắt')):
                list(agent.run(state))
            self.assertFalse(state['orchestration']['plan']['need_web'])

if __name__=='__main__':unittest.main()
