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

    def test_read_target_and_element_given_apart_name_one_object(self):
        rows=commands_from_json(json.dumps([{'command':'read','args':[{'ref':'g.Materials'},{'index':2}]},
                                            {'command':'read','args':[{'ref':'g.Materials'},0]}]))
        self.assertEqual(rows[0]['args'],[{'ref':'g.Materials','index':2}])
        self.assertEqual(rows[1]['args'],[{'ref':'g.Materials','index':0}])
        for rows in ([{'command':'read','args':[{'ref':'g.Materials'},{'index':-1}]}],
                     [{'command':'read','args':[{'ref':'g.Materials'},'first']}],
                     [{'command':'setproperties','args':[{'ref':'mat'},{'index':0}]}]):
            with self.assertRaises(ValueError):commands_from_json(json.dumps(rows))

    def test_reading_a_collection_names_its_elements(self):
        class Listable:
            def __init__(self,names):self._names=names
            def __len__(self):return len(self._names)
            def __getitem__(self,i):return SimpleNamespace(Name=SimpleNamespace(value=self._names[i]))
        g=SimpleNamespace(Materials=Listable(['Silt','Sand']))
        result=execute_commands(Mock(),g,commands_from_json(json.dumps(
            [{'command':'read','args':[{'ref':'g.Materials'}]}])))
        value=result['results'][0]['value']
        self.assertEqual(value['count'],2)
        self.assertTrue(value['items'][0].startswith('Silt '))
        self.assertTrue(value['items'][1].startswith('Sand '))

    def test_geometry_built_off_the_soil_body_is_reported(self):
        def point(name,y):return SimpleNamespace(Name=SimpleNamespace(value=name),y=SimpleNamespace(value=y))
        levels=[0,-3,-15,-30]
        def level(borehole,i):
            if i>=len(levels):raise RuntimeError('no such level')
            return levels[i]
        g=SimpleNamespace(Boreholes=['bh'],getsoillayerlevel=level,
                          plate=Mock(return_value='Plate_1'),
                          Points=[point('Point_1',30),point('Point_2',-5)])
        result=execute_commands(Mock(),g,commands_from_json(json.dumps(
            [{'command':'plate','args':[[40,30],[40,14]]}])))
        self.assertTrue(result['ok'])
        self.assertIn('Point_1 (y=30)',result['warning'])
        self.assertNotIn('Point_2',result['warning'])
        g.Points=[point('Point_2',-5)]
        self.assertNotIn('warning',execute_commands(Mock(),g,commands_from_json(json.dumps(
            [{'command':'plate','args':[[40,-1],[40,-14]]}]))))

    def test_phase_log_code_is_explained(self):
        g=SimpleNamespace(Phase_6=SimpleNamespace(LogInfo=SimpleNamespace(value='24'),
                                                  Identification=SimpleNamespace(value='24')))
        result=execute_commands(Mock(),g,commands_from_json(json.dumps(
            [{'command':'read','args':[{'ref':'g.Phase_6.LogInfo'}]},
             {'command':'read','args':[{'ref':'g.Phase_6.Identification'}]}])))
        self.assertTrue(result['results'][0]['value'].startswith('24: '))
        self.assertIn('thấm',result['results'][0]['value'])
        self.assertNotIn(':',str(result['results'][1]['value']))

    def test_member_with_the_same_two_ends_is_not_created_twice(self):
        def pt(x,y):return SimpleNamespace(x=SimpleNamespace(value=x),y=SimpleNamespace(value=y))
        anchor=SimpleNamespace(Parent=SimpleNamespace(First=pt(40,27),Second=pt(31,21)))
        g=SimpleNamespace(NodeToNodeAnchors=[anchor],n2nanchor=Mock(return_value='NodeToNodeAnchor_2'))
        result=execute_commands(Mock(),g,commands_from_json(json.dumps(
            [{'command':'n2nanchor','args':[[31,21],[40,27]],'result':'a'},
             {'command':'n2nanchor','args':[40,23,31,17]}])))
        self.assertTrue(result['ok'])
        self.assertIn('skipped',result['results'][0])
        self.assertNotIn('skipped',result['results'][1])
        g.n2nanchor.assert_called_once_with(40,23,31,17)

    def test_endless_reads_are_refused_until_the_model_changes(self):
        from assistant.online_automation import _plaxis_read_stall,PLAXIS_READ_STALL_LIMIT
        state={}
        reads={'commands':json.dumps([{'command':'read','args':[{'ref':'g.Plates'}]},
                                      {'command':'tabulate','args':[{'ref':'g.Materials'}]}])}
        for _ in range(PLAXIS_READ_STALL_LIMIT):
            self.assertIsNone(_plaxis_read_stall(state,'plaxis_commands',reads))
        self.assertIn('không thay đổi mô hình',_plaxis_read_stall(state,'plaxis_commands',reads))
        build={'commands':json.dumps([{'command':'n2nanchor','args':[[40,27],[31,21]]},
                                      {'command':'read','args':[{'ref':'g.NodeToNodeAnchors'}]}])}
        self.assertIsNone(_plaxis_read_stall(state,'plaxis_commands',build))
        self.assertEqual(state['plaxis_read_streak'],0)
        self.assertIsNone(_plaxis_read_stall(state,'browser_search',reads))

    def test_generic_followup_does_not_replay_an_old_embankment_template(self):
        from assistant.online_automation import _plaxis_history_call
        state={'messages':[{'role':'assistant','tool_calls':[{'function':{'name':'plaxis_run_problem','arguments':{'version':'2d'}}}]},
                           {'role':'assistant','tool_calls':[{'function':{'name':'plaxis_commands','arguments':{'version':'3d'}}}]}]}
        self.assertIsNone(_plaxis_history_call('chạy lại',{'windows_apps_enabled':True},state,Mock(),Mock()))

    def test_verify_model_checks_actual_properties_and_does_not_claim_full_solution(self):
        g=SimpleNamespace(Soils=['Soil_1','Soil_2'],Project=SimpleNamespace(ModelType=SimpleNamespace(value=0)))
        rows=commands_from_json(json.dumps([{'command':'verify_model','args':[json.dumps([
            {'ref':'g.Soils','expected':2,'kind':'count'},
            {'ref':'g.Project.ModelType','expected':0,'tolerance':0}])]}]))
        result=execute_commands(Mock(),g,rows)
        self.assertTrue(result['ok']);self.assertTrue(result['model_verified'])
        self.assertNotIn('results_verified',result)
        g.Soils.append('Unexpected')
        result=execute_commands(Mock(),g,rows)
        self.assertFalse(result['ok']);self.assertEqual(result['failed_command'],'verify_model')

    def test_verify_model_rejects_expression_and_invalid_tolerance(self):
        for check in [{'ref':'g.Soils[0].__class__()','expected':0}, {'ref':'g.Soils','expected':1,'tolerance':-1}]:
            with self.assertRaises(ValueError):commands_from_json(json.dumps([{'command':'verify_model','args':[json.dumps([check])]}]))

    def test_raw_coordinate_args_pass_through_without_ref_wrapping(self):
        # prescribeddisplacement_line and similar geometry commands take raw coordinates
        for cmd,args in [('prescribeddisplacement_line',[0,0,10,10]),
                         ('linedispl',[0,0,10,10]),
                         ('polycurve',[0,0,10,10,20,0]),
                         ('line',[0,0,10,10]),
                         ('plate',[0,0,10,10])]:
            rows=commands_from_json(json.dumps([{'command':cmd,'args':args}]))
            self.assertEqual(rows[0]['args'],args)
        # dict with non-ref keys is rejected with a helpful message
        with self.assertRaises(ValueError) as ctx:
            commands_from_json(json.dumps([{'command':'prescribeddisplacement_line','args':[{'x':0,'y':0},{'x':10,'y':10}]}]))
        self.assertIn('trực tiếp',str(ctx.exception))
