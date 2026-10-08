import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assistant.plaxis_commands import commands_from_json,execute_commands
from assistant.plaxis_remote import PlaxisRemoteApp
from assistant.online_automation import parse_plan
from assistant.tools import EXTRA_TOOLS
from assistant.windows_apps import resume_automation,stop_automation


class PlaxisCommandTests(unittest.TestCase):
    def setUp(self):resume_automation()
    def tearDown(self):resume_automation()
    def test_general_api_builds_material_and_geometry_without_problem_template(self):
        material=SimpleNamespace(Identification='SoilMat_1')
        g=SimpleNamespace(soilmat=Mock(return_value=material),setproperties=Mock(return_value='OK'),
                          surface=Mock(return_value=('Surface_1','Plate_1')),
                          Soils=[SimpleNamespace(Material='Sand')])
        commands=[{'command':'soilmat','result':'mat'},
                  {'command':'setproperties','args':[{'ref':'mat'},'Identification','Sand','E50ref',43000]},
                  {'command':'surface','args':[[0,0,0],[50,0,0],[50,0,-20]],'result':'wall'},
                  {'command':'read','args':[{'ref':'wall','index':1}]},
                  {'command':'read','args':[{'ref':'g.Soils','index':0}],'result':'soil'},
                  {'command':'read','args':[{'ref':'soil.Material'}]}]
        result=execute_commands(Mock(),g,commands_from_json(json.dumps(commands)))
        self.assertTrue(result['ok']);self.assertEqual(result['results'][3]['value'],'Plate_1')
        self.assertEqual(result['results'][5]['value'],'Sand')
        g.setproperties.assert_called_once_with(material,'Identification','Sand','E50ref',43000)
    def test_python_expressions_and_file_commands_are_rejected(self):
        for rows in ([{'command':'exec','args':['bad']}],[{'command':'open','args':['C:/private']}],
                     [{'command':'read','args':[{'ref':'g.__class__'}]}],
                     [{'command':'read','args':[{'ref':'g.Soils[0]'}]}],
                     [{'command':'surface','args':[{'python':'eval()'}]}]):
            with self.assertRaises(ValueError):commands_from_json(json.dumps(rows))
    def test_error_stops_remaining_commands_and_reports_partial_execution(self):
        g=SimpleNamespace(point=Mock(return_value='Point_1'),soilmat=Mock(side_effect=RuntimeError('Unknown property')),
                          calculate=Mock())
        result=execute_commands(Mock(),g,[{'command':'point','args':[1,2,3]},
                                {'command':'soilmat'},{'command':'calculate'}])
        self.assertFalse(result['ok']);self.assertEqual(result['failed_step'],2)
        self.assertEqual(len(result['results']),1);self.assertTrue(result['uncertain'])
        g.point.assert_called_once();g.calculate.assert_not_called()
    def test_no_implicit_project_reset_and_stop_is_respected(self):
        server=Mock();g=SimpleNamespace(commands=Mock(return_value='surface, plate, phase'))
        self.assertTrue(execute_commands(server,g,[{'command':'commands'}])['ok'])
        server.new.assert_not_called()
        stop_automation()
        result=execute_commands(server,g,[{'command':'new_project'}])
        self.assertTrue(result['not_executed']);server.new.assert_not_called()
    def test_remote_targets_and_structured_plan_are_supported(self):
        raw=json.dumps({'tool':'plaxis_commands','arguments':{'version':'3d','target':'output',
                       'commands':[{'command':'read','args':[{'ref':'g.Phases'}]}]}})
        args=parse_plan(raw,[s for _,s in EXTRA_TOOLS])['arguments']
        app=PlaxisRemoteApp(None);plan=app.prepare('plaxis_commands',args)
        with patch('assistant.plaxis_remote._connect',return_value=(Mock(),SimpleNamespace(Phases=['Phase_1'])) ) as connect:
            result=app.commit(plan)
        self.assertTrue(result['ok']);connect.assert_called_once_with(10001,'PLAXIS output')
        self.assertEqual(result['results'][0]['value'],['Phase_1'])
    def test_connection_failure_is_not_a_partially_executed_model(self):
        app=PlaxisRemoteApp(None)
        plan=app.prepare('plaxis_commands',{'version':'3d','commands':'[{"command":"commands"}]'})
        with patch('assistant.plaxis_remote._connect',side_effect=RuntimeError('Chưa bật server')):
            result=app.commit(plan)
        self.assertTrue(result['not_executed']);self.assertFalse(result['ok'])

    def test_statistics_use_all_results_beyond_preview(self):
        g=SimpleNamespace(getresults=Mock(return_value=list(range(300))))
        result=execute_commands(Mock(),g,[{'command':'getresults','result':'values'},
            {'command':'summarize','args':[{'ref':'values'}]}])
        self.assertTrue(result['results'][0]['truncated'])
        self.assertEqual(result['results'][1]['value']['count'],300)
        self.assertEqual(result['results'][1]['value']['max'],299)

    def test_generic_followup_does_not_replay_an_old_embankment_template(self):
        from assistant.online_automation import _plaxis_history_call
        state={'messages':[{'role':'assistant','tool_calls':[{'function':{'name':'plaxis_run_problem','arguments':{'version':'2d'}}}]},
                           {'role':'assistant','tool_calls':[{'function':{'name':'plaxis_commands','arguments':{'version':'3d'}}}]}]}
        self.assertIsNone(_plaxis_history_call('chạy lại',{'windows_apps_enabled':True},state,Mock(),Mock()))
