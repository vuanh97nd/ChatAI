import asyncio
import time
import tempfile
import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage
from fastapi.testclient import TestClient
from assistant.plaxis_agent.agent import run_agent
from assistant.plaxis_agent.api import create_app
from assistant.plaxis_agent.runtime import NativeRuntime


class Model:
    def __init__(self,reply=None):self.calls=0;self.reply=reply
    def bind_tools(self,tools):self.tools=tools;return self
    async def ainvoke(self,messages):
        self.calls+=1
        if self.calls==1:
            return self.reply or AIMessage(content='',tool_calls=[{'id':'inspect1','name':'plaxis_safe_inspect','args':{'version':'2d'}}])
        return AIMessage(content='Đã đọc trạng thái; chưa xác minh trọn bài.')


class Runtime:
    def __init__(self):self.calls=[];self.closed=False
    async def call(self,name,args):self.calls.append((name,args));return {'ok':True}
    def close(self):self.closed=True


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_graph_executes_inspect_and_keeps_completion_unverified(self):
        model=Model();runtime=Runtime();events=[]
        result=await run_agent(model,runtime,'inspect','2d',4,asyncio.Event(),events)
        self.assertEqual(result['steps'],1)
        self.assertFalse(result['model_completion_verified'])
        self.assertEqual(runtime.calls[0][0],'plaxis_safe_inspect')

    async def test_other_product_tool_never_executes(self):
        model=Model(AIMessage(content='',tool_calls=[{'id':'bad','name':'plaxis_safe_inspect','args':{'version':'3d'}}]))
        runtime=Runtime();events=[]
        result=await run_agent(model,runtime,'inspect','2d',4,asyncio.Event(),events)
        self.assertTrue(result['halted']);self.assertEqual(runtime.calls,[])

    async def test_unknown_tool_is_blocked(self):
        model=Model(AIMessage(content='',tool_calls=[{'id':'bad','name':'exec','args':{'code':'bad'}}]))
        runtime=Runtime()
        result=await run_agent(model,runtime,'inspect','2d',4,asyncio.Event(),[])
        self.assertTrue(result['halted']);self.assertEqual(runtime.calls,[])

    async def test_native_worker_does_not_block_event_loop_and_serializes_calls(self):
        runtime=NativeRuntime(object());self.addCleanup(runtime.close)
        active=0;maximum=0
        def blocking(*args):
            nonlocal active,maximum
            active+=1;maximum=max(maximum,active)
            time.sleep(.05)
            active-=1
            return {'ok':True}
        heartbeat=False
        async def tick():
            nonlocal heartbeat
            await asyncio.sleep(.005);heartbeat=True
        with patch('assistant.plaxis_agent.runtime.execute',side_effect=blocking):
            calls=asyncio.gather(runtime.call('test',{}),runtime.call('test',{}))
            await tick()
            self.assertTrue(heartbeat);self.assertFalse(calls.done())
            await calls
        self.assertEqual(maximum,1)


class ApiTests(unittest.TestCase):
    def test_health_auth_validation_and_background_job(self):
        runtime=Runtime()
        with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'CHATAI_AGENT_LOG_DIR':folder}),TestClient(create_app(Model(),runtime,api_token='test-token')) as client:
            self.assertEqual(client.get('/health').status_code,200)
            self.assertEqual(client.post('/plaxis/jobs',json={'prompt':'inspect','version':'2d'}).status_code,401)
            headers={'Authorization':'Bearer test-token'}
            self.assertEqual(client.post('/plaxis/jobs',headers=headers,json={'prompt':'inspect','version':'4d'}).status_code,422)
            response=client.post('/plaxis/jobs',headers=headers,json={'prompt':'inspect','version':'2d'})
            self.assertEqual(response.status_code,202)
            url='/plaxis/jobs/'+response.json()['id']
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                data=client.get(url,headers=headers).json()
                if data['status'] in ('finished','failed'):break
                time.sleep(.01)
            self.assertEqual(data['status'],'finished')
            self.assertFalse(data['result']['model_completion_verified'])
            self.assertEqual(client.get('/plaxis/jobs/missing',headers=headers).status_code,404)
        self.assertTrue(runtime.closed)
