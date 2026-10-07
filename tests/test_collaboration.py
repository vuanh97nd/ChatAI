import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from assistant.agent import Agent
from assistant.storage import Store
from assistant.collaboration import collaboration_intent,collect_artifacts,choose_coder,existing_artifacts,refresh_artifacts
from assistant.tools import EXTRA_TOOLS
import test_app as fixtures


class CollaborationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd());self.root=Path(self.temp.name)
        self.allowed=self.root/'allowed';self.allowed.mkdir()
        self.image=self.allowed/'logo.png';Image.new('RGB',(32,24)).save(self.image)
        self.store=Store(self.root/'history.db');self.cid=self.store.create()
        self.cfg={'roots':[self.allowed],'default_model':'qwen2.5:7b','code_model':'qwen2.5-coder:7b',
                  'num_ctx':4096,'num_predict':1000,'temperature':.2,'max_rounds':8}
    def tearDown(self):self.temp.cleanup()
    def test_intent_needs_explicit_creation(self):
        self.assertEqual(collaboration_intent('Tạo ảnh logo và viết code HTML')['stage'],'media')
        self.assertIsNone(collaboration_intent('Viết code gửi ảnh')['media_tool'])
        self.assertIsNone(collaboration_intent('Không tạo ảnh, chỉ viết code')['media_tool'])
        self.assertFalse(collaboration_intent('Xin chào')['enabled'])
    def test_artifacts_are_real_verified_local_files(self):
        result={'ok':True,'images':[str(self.image),str(self.root/'missing.png')]}
        manifest=collect_artifacts(result,[self.allowed],'image_generate')
        self.assertEqual(len(manifest),1);self.assertEqual((manifest[0]['width'],manifest[0]['height']),(32,24))
        self.assertEqual(collect_artifacts(result,[self.root/'other'],'image_generate'),[])
        self.assertEqual(collect_artifacts({'ok':False,'images':[str(self.image)]},[self.allowed],'image_generate'),[])
        result['artifact_manifest']=manifest
        Image.new('RGB',(8,8)).save(self.image)
        self.assertEqual(collect_artifacts(result,[self.allowed],'image_generate'),[])
    def test_missing_coder_fallback_never_downloads(self):
        client=SimpleNamespace(list=lambda:SimpleNamespace(models=[]))
        model,note=choose_coder(client,'qwen2.5-coder:7b','qwen2.5:7b')
        self.assertEqual(model,'qwen2.5:7b');self.assertIn('Chưa tải',note)
    def build(self, deny=False, complex_question=False):
        outer=self
        class Client:
            requests=[]
            def list(self):return SimpleNamespace(models=[SimpleNamespace(model='qwen2.5-coder:7b')])
            def generate(self,**kwargs):pass
            def chat(self,**kwargs):
                if kwargs.get('format'):return {'message':{'content':json.dumps(dict(category='coding',creative=False,complex=complex_question,high_accuracy=False))}}
                if kwargs.get('stream') is False:
                    assert kwargs['model']=='qwen2.5-coder:7b'
                    assert 'specialist_handoff' in kwargs['messages'][-1]['content']
                    return {'message':{'content':'Bản code đã kiểm tra'}}
                self.requests.append(kwargs)
                if len(self.requests)==1:
                    return iter([fixtures.chunk('Không hiển thị nháp này',calls=[fixtures.FakeCall('image_generate',{'prompt':'a robot logo'})])])
                instruction=kwargs['messages'][0]['content']
                assert kwargs['model']=='qwen2.5-coder:7b'
                if not deny:assert str(outer.image) in instruction and 'sha256' in instruction
                else:assert 'denied' in instruction and str(outer.image) not in instruction
                assert not any(s['function']['name']=='image_generate' for s in kwargs['tools'])
                return iter([fixtures.chunk('```python\nprint("code sử dụng ảnh")\n```')])
        class Caps:
            schemas=[schema for module,schema in EXTRA_TOOLS if schema['function']['name']=='image_generate']
            def prepare(self,name,args):return {'action':name,'prompts':[args['prompt']]}
            def commit(self,plan):return {'ok':True,'images':[str(outer.image)]}
        client=Client();client.requests=[]
        agent=Agent(client,None,self.cfg,self.store,self.cid,Caps())
        state=self.store.load(self.cid);agent.start(state,'Tạo ảnh logo và viết code Python dùng ảnh đó','qwen2.5:7b');state['ui_mode']=2;state['media_prompt_en']='a robot logo'
        events=list(agent.run(state))
        self.assertIsNotNone(state['pending']);self.assertEqual(state['collaboration']['stage'],'media')
        self.assertFalse(any(e['type']=='token' for e in events))
        agent.approve(state,not deny);events=list(agent.run(state))
        self.assertFalse(state['running']);self.assertEqual(state['collaboration']['active_model'],'qwen2.5-coder:7b')
        self.assertEqual(state['model'],'qwen2.5:7b')
        self.assertTrue(any('bàn giao' in e.get('text','') for e in events))
        return state
    def test_generate_approve_and_coder_handoff(self):
        state=self.build();self.assertEqual(state['collaboration']['media_status'],'created')
        self.assertEqual(len(existing_artifacts(state,[self.allowed])),1)
    def test_denied_media_still_reaches_coder_honestly(self):
        state=self.build(True);self.assertEqual(state['collaboration']['media_status'],'denied')
        self.assertEqual(state['collaboration']['artifacts'],[])
    def test_normal_chat_image_stays_with_selected_model(self):
        class Client:
            requests=[]
            def list(self):return SimpleNamespace(models=[SimpleNamespace(model='qwen2.5-coder:7b')])
            def generate(self,**kwargs):pass
            def chat(self,**kwargs):
                if kwargs.get('format'):return {'message':{'content':json.dumps(dict(category='coding',creative=False,complex=False,high_accuracy=False))}}
                self.requests.append(kwargs)
                if len(self.requests)==1:
                    assert kwargs['model']=='gemma3:4b';assert kwargs['messages'][-1].get('images')
                    return iter([fixtures.chunk('Quan sát: thanh bên trái màu tối.')])
                assert kwargs['model']=='qwen2.5-coder:7b'
                assert not any(m.get('images') for m in kwargs['messages'])
                assert 'thanh bên trái màu tối' in kwargs['messages'][0]['content']
                return iter([fixtures.chunk('Code theo mô tả bố cục.')])
        client=Client();client.requests=[];agent=Agent(client,None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Viết code HTML theo ảnh','gemma3:4b',images=[__import__('base64').b64encode(self.image.read_bytes()).decode('ascii')])
        events=list(agent.run(state));text=''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertIn('Quan sát:',text);self.assertEqual(len(client.requests),1)
        self.assertFalse(state['collaboration']['enabled'])
        self.assertIsNone(state.get('orchestration'))

    def test_revalidate_after_handoff_detects_deleted_file(self):
        plan={'artifacts':collect_artifacts({'ok':True,'images':[str(self.image)]},[self.allowed],'image_generate'),'media_status':'created'}
        self.image.unlink();self.assertTrue(refresh_artifacts(plan,[self.allowed]))
        self.assertEqual(plan['artifacts'],[]);self.assertEqual(plan['media_status'],'changed_or_missing')

    def test_selected_coder_is_preserved(self):
        client=SimpleNamespace()
        self.assertEqual(choose_coder(client,'qwen2.5-coder:7b','deepseek-coder:33b'),('deepseek-coder:33b',None))

    def test_discussion_does_not_request_media(self):
        self.assertIsNone(collaboration_intent('Đề xuất tạo ảnh logo và code HTML')['media_tool'])

    def test_complex_coder_review_receives_handoff(self):
        state=self.build(complex_question=True)
        self.assertEqual(state['review_status'],'completed')
        self.assertEqual(state['messages'][-1]['content'],'Bản code đã kiểm tra')
