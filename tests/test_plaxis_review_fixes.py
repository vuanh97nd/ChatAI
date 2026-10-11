import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assistant.plaxis_commands import execute_commands
from assistant.plaxis_remote import resolve_port,run_plaxis_problem
from assistant.online_automation import calculate_unverified
from assistant.windows_apps import resume_automation


class ReviewFixTests(unittest.TestCase):
    def setUp(self):resume_automation()

    def test_opposite_product_port_is_not_used(self):
        with patch('assistant.plaxis_remote.detect_ports',side_effect=lambda v: {'input':10000} if v=='2d' else {}):
            with self.assertRaises(RuntimeError):resolve_port('3d','input')

    def test_populated_project_is_preserved(self):
        server=Mock();g=SimpleNamespace(Boreholes=['existing'])
        with patch('assistant.plaxis_remote.resolve_port',return_value=(10000,True)),patch('assistant.plaxis_remote._connect',return_value=(server,g)),patch('assistant.plaxis_remote._exec_script_on_server') as execute:
            result=run_plaxis_problem('anything')
        self.assertFalse(result['executed']);server.new.assert_not_called();execute.assert_not_called()

    def test_empty_phase_is_blocked_on_every_attempt(self):
        g=SimpleNamespace(calculate=Mock())
        session={'aliases':{},'created':{}}
        with patch('assistant.plaxis_commands._empty_phases',return_value=['Phase_1 không đổi']):
            for _ in range(2):
                result=execute_commands(Mock(),g,[{'command':'calculate','args':[]}],session=session)
                self.assertFalse(result['ok'])
        g.calculate.assert_not_called()

    def test_mutation_after_verification_invalidates_batch(self):
        g=SimpleNamespace(Project=SimpleNamespace(ModelType=SimpleNamespace(value=0)),point=Mock(return_value='Point_1'))
        verify={'command':'verify_model','args':[json.dumps([{'ref':'g.Project.ModelType','expected':0}])]}
        write={'command':'point','args':[1,2]}
        self.assertFalse(execute_commands(Mock(),g,[verify,write])['model_verified'])
        self.assertTrue(execute_commands(Mock(),g,[write,verify])['model_verified'])

    def test_repeated_calculate_does_not_bypass_manual_check(self):
        state={'tutorial':{'title':'Test'},'messages':[{'role':'user','content':'tính'}]}
        args={'commands':[{'command':'calculate'}]}
        for _ in range(2):self.assertIsNotNone(calculate_unverified(state,args))

    def test_verification_before_new_write_does_not_authorize_calculation(self):
        state={'tutorial':{'title':'Test'},'messages':[]}
        rows=[{'command':'verify_model'},{'command':'point','args':[1,2]},{'command':'calculate'}]
        self.assertIsNotNone(calculate_unverified(state,{'commands':rows}))

    def test_unfinished_phase_never_reads_output(self):
        g=SimpleNamespace(Boreholes=[],Soillayers=[],Materials=[],Points=[],Soils=[],Phases=['InitialPhase'])
        server=Mock()
        with patch('assistant.plaxis_remote.resolve_port',return_value=(10000,True)),patch('assistant.plaxis_remote._connect',return_value=(server,g)) as connect,patch('assistant.plaxis_remote._exec_script_on_server',return_value=''),patch('assistant.plaxis_remote.phase_diagnostics',return_value=[{'name':'InitialPhase','status':0,'log':''}]):
            result=run_plaxis_problem('anything')
        self.assertFalse(result['executed']);self.assertEqual(connect.call_count,1)
        server.new.assert_not_called()

    def test_foundation_template_declares_plane_strain(self):
        from assistant.plaxis_app import _generate_script,_validate_problem
        problem=_validate_problem(json.dumps({'type':'foundation_settlement','footing_width':2,'footing_depth':0,'load':100,'soil_layers':[{'E':10000,'nu':.3,'gamma':17,'c':1,'phi':30,'thickness':10}]}))
        script=_generate_script(problem,'2d',10000,'Test')
        self.assertIn('g.setproperties(g.Project, "ModelType", "Plane strain")',script)
        self.assertIn('footing_load.qy_start = -50.00',script)

    def test_second_calculation_requires_reverification_after_write(self):
        state={'tutorial':{'title':'Test'},'messages':[]}
        rows=[{'command':'verify_model'},{'command':'calculate'},{'command':'point','args':[1,2]},{'command':'calculate'}]
        self.assertIsNotNone(calculate_unverified(state,{'commands':rows}))
