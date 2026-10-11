import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from langchain_core.messages import AIMessage
from assistant.geo_solver import geo_calculate
from assistant.plaxis_agent.tools import execute
from assistant.plaxis_agent.schemas import Criterion
from assistant.plaxis_agent.evidence import review
from assistant.plaxis_agent.project_memory import ProjectMemory
from assistant.plaxis_agent.agent import run_agent


class EvidenceTests(unittest.TestCase):
    def test_nonfinite_and_boolean_inputs_fail(self):
        for value in [float('nan'), float('inf'), True, 'NaN']:
            result = geo_calculate('settlement', json.dumps(dict(H=value,e0=1,Cc=.2,sigma0=100,delta_sigma=50)))
            self.assertIn('error', result)

    def test_tool_schema_rejects_missing_or_nonfinite_before_execution(self):
        from assistant.plaxis_agent.tools import prepare
        for params in [{}, dict(H=True,e0=1,Cc=.2,sigma0=100,delta_sigma=50), dict(H=float('inf'),e0=1,Cc=.2,sigma0=100,delta_sigma=50)]:
            with self.assertRaises(ValueError):
                prepare('plaxis_safe_geo_calculate', dict(version='2d',formula='settlement',params=params))

    def test_calculation_and_units_are_real(self):
        result = execute(None, 'plaxis_safe_geo_calculate', dict(version='2d', formula='settlement',params=dict(H=10,e0=1,Cc=.2,sigma0=100,delta_sigma=50)))
        self.assertTrue(result['ok'])
        self.assertAlmostEqual(result['metrics']['S_m']['value'], .1761)
        criterion = Criterion(metric='S_m', operator='le', target=.2, unit='m')
        self.assertTrue(review([{'result':result}], [criterion])['passed'])
        criterion.unit = 'mm'
        self.assertFalse(review([{'result':result}], [criterion])['passed'])
        self.assertFalse(review([{'result':{'ok':True,'answer':'passed'}}], [criterion])['passed'])

    def test_project_memory_isolated_and_not_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ProjectMemory(Path(directory)/'memory.db')
            memory.save('a','2d',[{'tool':'write','arguments':{'code':'bad'},'result':{'ok':True}}],{})
            self.assertNotIn('arguments',memory.load('a','2d')['events'][0])
            self.assertEqual(memory.load('a','3d'),{})
            self.assertEqual(memory.load('b','2d'),{})


class CriticTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_numeric_criterion_recalculates_with_bounded_tools(self):
        class Model:
            calls = 0
            def bind_tools(self, tools): return self
            async def ainvoke(self, messages):
                self.calls += 1
                if self.calls in (1,3):
                    return AIMessage(content='',tool_calls=[{'id':str(self.calls),'name':'plaxis_safe_geo_calculate','args':{'version':'2d','formula':'settlement','params':{}}}])
                return AIMessage(content='done')
        class Runtime:
            calls = 0
            async def call(self, name, args):
                self.calls += 1
                return {'ok':True,'metrics':{'S_m':{'value':.3 if self.calls==1 else .1,'unit':'m'}}}
        result = await run_agent(Model(),Runtime(),'calculate','2d',4,asyncio.Event(),[],[Criterion(metric='S_m',operator='le',target=.2,unit='m')])
        self.assertTrue(result['criteria_review']['passed'])
        self.assertEqual(result['steps'],2)
        self.assertFalse(result['model_completion_verified'])

    async def test_jobs_load_project_and_rag_without_trusting_old_inspect(self):
        from assistant.plaxis_agent.jobs import Jobs
        from assistant.plaxis_agent.schemas import JobRequest
        from unittest.mock import AsyncMock, patch
        class Memory:
            def load(self, *args): return {'events':[{'tool':'plaxis_safe_inspect','result':{'ok':True}}]}
            def save(self, *args): self.saved = args
        class Knowledge:
            def rag_search(self, query): return {'sources':[{'text':'source', 'page':1, 'sha256':'abc'}]}
        class Runtime:
            def close(self): pass
        memory=Memory()
        jobs=Jobs(object(),Runtime(),memory=memory,knowledge=Knowledge())
        with patch('assistant.plaxis_agent.jobs.run_agent', new=AsyncMock(return_value={'halted':False,'limit_reached':False})) as run:
            job=jobs.submit(JobRequest(prompt='test',version='2d',project_id='p'))
            await asyncio.gather(*list(jobs.tasks))
            self.assertEqual(run.call_args.args[-1]['retrieved_sources_untrusted']['sources'][0]['page'],1)
            self.assertEqual(job.events, [])
            self.assertEqual(memory.saved[0],'p')
        await jobs.close()
