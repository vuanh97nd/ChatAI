import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
from assistant.plaxis_commands import commands_from_json,execute_commands
from assistant.plaxis_stage_guard import active,StageGuardError
from assistant.windows_apps import resume_automation

class PhaseProperty:
    def __init__(self,values):self.values=list(values);self.reads=0
    def __getitem__(self,phase):
        self.reads+=1
        return NS(value=self.values[min(self.reads-1,len(self.values)-1)])

class ProgressTests(unittest.TestCase):
    def setUp(self):resume_automation()
    def test_progress_enums_normalize_only_unambiguous_stage_aliases(self):
        from assistant.plaxis_progress import specification
        result=specification(json.dumps({'source':'Manual','checks':[
            {'ref':'g.Materials','expected':2,'stage':' Material ','kind':' COUNT '},
            {'ref':'g.Soil_1_1.Active','phase':'g.Phase_1','expected':False,'stage':'staged_construction'}]}))
        self.assertEqual(result['checks'][0]['stage'],'materials')
        self.assertEqual(result['checks'][0]['kind'],'count')
        self.assertEqual(result['checks'][1]['stage'],'activation')
        self.assertEqual(result['checks'][1]['kind'],'value')

    def test_wrong_guard_kind_and_phase_in_stage_have_actionable_errors(self):
        from assistant.plaxis_progress import specification
        check={'ref':'g.Soil_1_1.Active','phase':'g.Phase_1','expected':False,'stage':'activation','kind':'soil'}
        with self.assertRaisesRegex(ValueError,r'checks\[1\].kind=.*soil.*verify_stage'):
            specification(json.dumps({'source':'Manual','checks':[check]}))
        check.update(kind='value',stage='Phase_1')
        with self.assertRaisesRegex(ValueError,r'checks\[1\].stage=.*phase_1.*Tên Phase_1'):
            specification(json.dumps({'source':'Manual','checks':[check]}))

    def test_phase_material_and_numeric_properties_are_read_without_active_coercion(self):
        g=self.model()
        class Property:
            def __init__(self,value):self.value=value
            def __getitem__(self,phase):return NS(value=self.value)
        g.Soil_1_1.Material=Property(NS(Name='Sand'))
        g.Soil_1_1.Load=Property(-10.0)
        g.Soil_1_1.Unknown=Property(None)
        spec={'source':'Manual','checks':[
            {'ref':'g.Soil_1_1.Material','phase':'g.Phase_1','expected':'Sand','stage':'materials'},
            {'ref':'g.Soil_1_1.Load','phase':'g.Phase_1','expected':-10.,'stage':'phases'},
            {'ref':'g.Soil_1_1.Unknown','phase':'g.Phase_1','expected':0.,'stage':'phases'}]}
        result=execute_commands(Mock(),g,commands_from_json(json.dumps([{'command':'inspect_progress','args':spec}])))
        report=result['results'][0]['value']
        self.assertEqual(len(report['verified']),2)
        self.assertEqual(len(report['unreadable']),1)
        self.assertEqual(report['missing_or_wrong'],[])

    def test_active_expected_remains_strict_and_phase_count_is_rejected(self):
        from assistant.plaxis_progress import specification
        for value in ('false',0,None):
            with self.assertRaises(ValueError):
                specification(json.dumps({'source':'Manual','checks':[{'ref':'g.Soil_1_1.Active','phase':'g.Phase_1','expected':value}]}))
        with self.assertRaisesRegex(ValueError,'bỏ phase'):
            specification(json.dumps({'source':'Manual','checks':[{'ref':'g.Soils','phase':'g.Phase_1','expected':1,'kind':'count'}]}))
    def model(self,states=[True]):
        phase=NS(Name='Phase_1');soil=NS(Name='Soil_1_1',Active=PhaseProperty(states))
        return NS(Project=NS(ModelType=0),Soils=[soil],Phases=[phase],Materials=[],Plates=[],Soil_1_1=soil,Phase_1=phase)
    def spec(self):return {'source':'Manual bài 7, staged construction', 'checks':[
        {'ref':'Project.ModelType','expected':0,'stage':'project'},
        {'ref':'g.Plates','kind':'count','expected':2,'stage':'geometry'},
        {'ref':'Soil_1_1.Active','phase':'Phase_1','expected':True,'stage':'activation'}]}
    def run_progress(self,g,command='inspect_progress',session=None):
        rows=commands_from_json(json.dumps([{'command':command,'args':self.spec()}]))
        result=execute_commands(Mock(),g,rows,session=session)
        self.assertTrue(result['ok'],result)
        return result['results'][0]['value']
    def test_live_read_ignores_stale_alias_and_preserves_verified_parts(self):
        g=self.model()
        report=self.run_progress(g,session={'aliases':{'Soil_1_1':NS(Active=None)},'created':{}})
        self.assertEqual(len(report['verified']),2)
        self.assertEqual(report['missing_or_wrong'][0]['ref'],'g.Plates')
        self.assertEqual(report['inventory']['Soils']['names'],['Soil_1_1'])
        self.assertFalse(report['model_completion_verified'])
    def test_none_is_unknown_not_missing_or_false_and_retry_bounded(self):
        g=self.model([None]);report=self.run_progress(g)
        self.assertEqual(report['unreadable'][0]['ref'],'Soil_1_1.Active')
        self.assertEqual(g.Soil_1_1.Active.reads,2)
        self.assertNotIn('actual',report['unreadable'][0])
    def test_transient_none_recovers_without_writes(self):
        g=self.model([None,True]);report=self.run_progress(g)
        self.assertEqual(len(report['verified']),2)
        self.assertEqual(g.Soil_1_1.Active.reads,2)
    def test_repair_plan_keeps_matches_and_requires_activation_guard(self):
        g=self.model([False]);plan=self.run_progress(g,'plan_resume')
        self.assertEqual(plan['keep'][0]['ref'],'Project.ModelType')
        self.assertEqual(plan['actions'][-1]['action'],'verify_stage_then_set')
        self.assertFalse(plan['executable'])
        self.assertEqual(g.Soil_1_1.Active.values,[False])
    def test_mode_unavailable_and_unprovided_checks_not_verified(self):
        report=self.run_progress(self.model())
        self.assertEqual(report['inventory']['Boreholes']['status'],'unreadable')
        self.assertIn('mesh',[r['stage'] for r in report['unverified']])
    def test_stale_name_unknown_not_proof_of_absent_geometry(self):
        g=self.model();del g.Soil_1_1
        report=self.run_progress(g)
        self.assertEqual(report['unreadable'][0]['ref'],'Soil_1_1.Active')
        self.assertEqual(report['inventory']['Soils']['count'],1)
    def test_string_boolean_not_coerced(self):
        g=self.model(['False'])
        with self.assertRaises(StageGuardError):active(g.Soil_1_1,g.Phase_1)
        self.assertEqual(g.Soil_1_1.Active.reads,1)
    def test_progress_does_not_block_partial_verified_report_or_allow_completion(self):
        from assistant.online_automation import unverified_completion,calculate_unverified
        state={'tutorial':{'number':7,'title':'Manual'},'messages':[{'role':'assistant','tool_calls':[{'function':{'name':'plaxis_commands','arguments':{'commands':json.dumps([{'command':'phase'}])}}}]}]}
        self.assertIsNone(unverified_completion('Đã xác minh địa tầng; Active chưa đọc được.',state))
        self.assertIsNotNone(unverified_completion('Đã hoàn tất mô hình đúng manual.',state))
        self.assertIsNone(calculate_unverified(state,{'commands':json.dumps([{'command':'inspect_progress'}])}))
        self.assertIsNotNone(calculate_unverified(state,{'commands':json.dumps([{'command':'calculate'}])}))
