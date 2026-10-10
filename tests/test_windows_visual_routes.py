"""Capture the real online planning payload; no provider or real desktop calls."""
import json
import unittest
from types import SimpleNamespace
import test_online_automation as online_fixtures
import test_windows_visual as visual_fixtures
from assistant.tools import EXTRA_TOOLS
from assistant.windows_visual import VISUAL_TOOLS

class VisualRouteTest(unittest.TestCase):
    def setUp(self):
        self.case=online_fixtures.OnlineAutomationTest();self.case.setUp();self.addCleanup(self.case.tearDown)
        self.agent=self.case.agent
        self.agent.plaxis_remote=SimpleNamespace()
        self.agent.schemas += [s for module,s in EXTRA_TOOLS if module=='plaxis_remote']
    def start(self):
        self.agent.start(self.case.state,'Kiểm tra PLAXIS Tunnel_1 hiện có','DeepSeek Flash','test')
        self.case.state['queue']=[]
        self.case.state['plaxis_general_mode']=True
    def test_visual_schemas_survive_in_actual_chat_payload_for_plaxis(self):
        self.start()
        self.case.responses=[json.dumps({'answer':'Chưa thao tác mô hình.','tool':'','arguments':{}})]
        list(self.agent.run(self.case.state))
        system=next(m['content'] for m in self.case.requests[0] if m['role']=='system' and 'Công cụ: ' in m['content'])
        specs,_=json.JSONDecoder().raw_decode(system.split('Công cụ: ',1)[1])
        names={s['function']['name'] for s in specs}
        self.assertTrue(VISUAL_TOOLS <= names)
        self.assertIn('plaxis_commands',names)
        self.assertNotIn('plaxis_run_problem',names)
        self.assertTrue(all(self.agent.component(n) is self.agent.windows for n in VISUAL_TOOLS))
    def test_capture_and_input_dispatch_with_post_action_image_in_next_request(self):
        desktop=visual_fixtures.VisualTest();desktop.setUp();self.addCleanup(desktop.tearDown)
        desktop.cfg['windows_apps_auto_execute']=True
        self.case.cfg['windows_apps_auto_execute']=True
        self.agent.windows=desktop.apps
        self.start()
        received=[]
        def chat(model,messages,**kwargs):
            received.append(messages)
            if len(received)==1:
                plan={'answer':'','tool':'windows_capture','arguments':{'session':desktop.session}}
            elif len(received)==2:
                message=self.case.state['messages'][-1]
                observation=json.loads(message['content'])['observation']
                plan={'answer':'','tool':'windows_input','arguments':{'session':desktop.session,'observation':observation,'operation':'click','x':10,'y':20}}
            else:plan={'answer':'Đã đọc ảnh giả lập sau thao tác.','tool':'','arguments':{}}
            return {'message':{'content':json.dumps(plan)}}
        self.agent.client.chat=chat
        list(self.agent.run(self.case.state))
        self.assertEqual(len(desktop.backend.actions),1)
        self.assertEqual(desktop.backend.captures,2)
        self.assertEqual(desktop.apps.backend.launches,[])
        for request,tool in [(received[1],'windows_capture'),(received[2],'windows_input')]:
            images=[m['content'] for m in request if isinstance(m.get('content'),list)]
            self.assertEqual(len(images),1)
            self.assertIn(tool,images[0][0]['text'])
            self.assertTrue(images[0][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))

if __name__=='__main__':unittest.main()
