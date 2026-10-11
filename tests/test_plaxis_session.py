import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from assistant.plaxis_session import bind,live_scope
from assistant.plaxis_commands import execute_commands,run_batch,_SESSIONS
from assistant.online_automation import remember_working_forms
from assistant.procedure_memory import ProcedureMemory
from assistant.storage import Store
from assistant.windows_apps import resume_automation


class PlaxisSessionTests(unittest.TestCase):
    def setUp(self):
        resume_automation()
        _SESSIONS.clear()

    def test_same_live_scope_keeps_aliases_changed_soils_or_project_invalidates(self):
        g=NS(Project=NS(_guid='project'),InitialPhase=NS(_guid='initial'),Soils=[NS(_guid='soil')])
        session={}
        scope=live_scope(g,'2d',10000)
        bind(session,scope)
        session.update(aliases={'soil':g.Soils[0]},created={'soil':'polygon'},phase_log={'Phase_1':{}},stage_permit={})
        self.assertFalse(bind(session,scope))
        self.assertIn('soil',session['aliases'])
        g.Soils=[NS(_guid='soil-after-remesh')]
        self.assertTrue(bind(session,live_scope(g,'2d',10000)))
        self.assertEqual(session['aliases'],{})
        self.assertEqual(session['phase_log'],{})
        self.assertNotIn('stage_permit',session)
        self.assertNotEqual(scope,live_scope(g,'3d',10000))
        g.Project=NS(_guid='new-project')
        self.assertNotEqual(scope,live_scope(g,'2d',10000))

    def test_mesh_clears_all_old_aliases_before_next_command_even_in_same_batch(self):
        g=NS(Soils=[],mesh=Mock(return_value='OK'))
        session={'aliases':{'oldsoil':NS()},'created':{'oldsoil':'polygon'},'phase_log':{'Phase_1':{}},'stage_permit':{}}
        result=execute_commands(Mock(),g,[{'command':'mesh','args':[.06]},
                                       {'command':'read','args':[{'ref':'oldsoil'}]}],session=session)
        self.assertEqual(g.mesh.call_count,1)
        self.assertIn('error',result['results'][1])
        self.assertEqual(session['aliases'],{})
        self.assertEqual(session['phase_log'],{})
        self.assertIn('chưa được định nghĩa',result['results'][1]['error'])

    def test_same_project_rerun_can_reuse_valid_alias_but_external_remesh_cannot(self):
        g=NS(Project=NS(_guid='p'),InitialPhase=NS(_guid='i'),Soils=[NS(_guid='s')],
             soilmat=Mock(return_value=NS(_guid='mat',Identification='Clay')))
        with patch('assistant.plaxis_commands.model_snapshot',return_value='actual'),patch('assistant.plaxis_commands._soils_without_material',return_value=[]):
            first=run_batch(Mock(),g,[{'command':'soilmat','args':[],'result':'clay'}],port=10000,version='2d')
            second=run_batch(Mock(),g,[{'command':'read','args':[{'ref':'clay'}]}],port=10000,version='2d')
            self.assertTrue(second['ok'])
            g.Soils=[NS(_guid='remeshed')]
            third=run_batch(Mock(),g,[{'command':'read','args':[{'ref':'clay'}]}],port=10000,version='2d')
        self.assertTrue(first['runtime_scope'])
        self.assertIn('error',third['results'][0])
        self.assertTrue(third['references_invalidated'])
        self.assertEqual(g.soilmat.call_count,1)

    def test_learned_refs_and_progress_do_not_survive_model_invalidation(self):
        state={'messages':[{'role':'user','content':'PLAXIS bài 7'}],
               'plaxis_learned':['oldsoil.Active'],'plaxis_learned_scope':'old',
               'procedure_progress':{'task':'PLAXIS bài 7','runtime_scope':'old','steps':[{'command':'plate'}]}}
        call={'function':{'name':'plaxis_commands','arguments':{'version':'2d','commands':json.dumps([{'command':'inspect_progress','args':['{}']}])}}}
        result={'ok':True,'runtime_scope':'new','references_invalidated':True,
                'environment':'2d v22.1','results':[{'step':1,'value':{'read_only':True}}]}
        remember_working_forms(state,call,result)
        self.assertEqual(state['plaxis_learned'],[])
        with tempfile.TemporaryDirectory() as folder:
            memory=ProcedureMemory(Store(Path(folder)/'db'))
            memory.remember('a',state,call,result)
            self.assertEqual([r['command'] for r in state['procedure_progress']['steps']],['inspect_progress'])
            self.assertEqual(state['procedure_progress']['steps'][0]['status'],'observed')
            state['procedure_environment']='3d v2024'
            context=memory.context('a','PLAXIS bài 7',state=state)
            self.assertIn('unverified_environment_syntax_only',context)
            self.assertIn('"replay_allowed": false',context)

    def test_new_project_discards_old_log_but_keeps_objects_created_after_reset(self):
        g=NS(Project=NS(_guid='p'),InitialPhase=NS(_guid='i'),Soils=[],
             soilmat=Mock(return_value=NS(_guid='mat',Identification='Clay')))
        server=Mock()
        with patch('assistant.plaxis_commands.model_snapshot',return_value='actual'):
            run_batch(server,g,[{'command':'new_project','args':[]},
                                {'command':'soilmat','args':[],'result':'clay'}],port=10000,version='2d')
            read=run_batch(server,g,[{'command':'read','args':[{'ref':'clay'}]}],port=10000,version='2d')
        self.assertNotIn('error',read['results'][0])
        self.assertEqual(g.soilmat.call_count,1)
        server.new.assert_called_once()
