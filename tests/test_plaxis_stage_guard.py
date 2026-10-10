import json
import unittest
from types import SimpleNamespace as Obj
from assistant.plaxis_commands import execute_commands,commands_from_json
from assistant.windows_apps import resume_automation,stop_automation

class Ref:
    def __init__(self,name,**props):self.Name=name;self.__dict__.update(props)
    def __str__(self):return self.Name
    def __hash__(self):return id(self)

class StageGuardTest(unittest.TestCase):
    def setUp(self):
        resume_automation()
        self.initial=Ref('InitialPhase')
        self.phase=Ref('Phase_1',PreviousPhase=self.initial)
        self.other_phase=Ref('Phase_2',PreviousPhase=self.initial)
        self.soil=Ref('Soil_1',Parent=Ref('Polygon_1',BoundingBox=Obj(xMin=10,xMax=15,yMin=-5,yMax=0)),Active={self.initial:True,self.phase:True,self.other_phase:True})
        self.outside=Ref('Soil_2',Parent=Ref('Polygon_2',BoundingBox=Obj(xMin=0,xMax=10,yMin=-10,yMax=0)),Active={self.initial:True,self.phase:True,self.other_phase:True})
        self.calls=[]
        def set_value(prop,phase,value):
            self.calls.append((prop,phase,value));prop[phase]=value
        self.g=Obj(Soil_1=self.soil,Soil_2=self.outside,Soils=[self.soil,self.outside],
                   InitialPhase=self.initial,Phase_1=self.phase,Phase_2=self.other_phase,set=set_value,
                   activate=lambda *a:self.calls.append(a),deactivate=lambda *a:self.calls.append(a),
                   setproperties=lambda *a:self.calls.append(a),gotostages=lambda:None)
        self.session={'aliases':{},'created':{}}
        self.spec={'target':'Soil_1','phase':'Phase_1','parent_phase':'InitialPhase','before':True,
                   'parent_active':True,'after':False,'shape':'box','region':{'x':[10,20],'y':[-5,0]},
                   'source':'Fixture manual, excavation stage 1'}
    def tearDown(self):resume_automation()
    def run_rows(self,rows):return execute_commands(Obj(),self.g,commands_from_json(json.dumps(rows)),session=self.session)
    def verify(self,**changes):return self.run_rows([{'command':'verify_stage','args':[json.dumps(dict(self.spec,**changes))]}])
    def change(self,target='Soil_1',phase='Phase_1',after=False):
        return self.run_rows([{'command':'set','args':[{'ref':target+'.Active'},{'ref':phase},after]}])
    def test_unverified_change_is_blocked_before_api(self):
        result=self.change()
        self.assertFalse(result['ok']);self.assertFalse(result['command_started'])
        self.assertIn('verify_stage',result['error']);self.assertEqual(self.calls,[])
    def test_inside_box_correct_phase_changes_once_and_reads_back(self):
        self.assertTrue(self.verify()['ok'])
        result=self.change()
        self.assertTrue(result['ok'],result)
        readback=result['results'][0]['value']['stage_readback']
        self.assertTrue(readback['verified']);self.assertTrue(readback['other_soils_unchanged'])
        self.assertFalse(self.soil.Active[self.phase]);self.assertTrue(self.outside.Active[self.phase])
        self.assertFalse(self.change()['ok']);self.assertEqual(len(self.calls),1)
    def test_same_inside_candidate_does_not_authorize_another_soil(self):
        self.assertTrue(self.verify()['ok'])
        result=self.change(target='Soil_2')
        self.assertFalse(result['ok']);self.assertEqual(self.calls,[])
    def test_phase_or_direction_cannot_change_after_verification(self):
        for args in [dict(phase='Phase_2'),dict(after=True)]:
            self.assertTrue(self.verify()['ok'])
            self.assertFalse(self.change(**args)['ok'])
        self.assertEqual(self.calls,[])
    def test_outside_and_boundary_crossing_are_rejected(self):
        for low,high in [(0,5),(5,15),(10,21)]:
            self.soil.Parent.BoundingBox.xMin=low;self.soil.Parent.BoundingBox.xMax=high
            self.assertFalse(self.verify()['ok'])
        self.assertEqual(self.calls,[])
    def test_phase_parent_mismatch_blocks(self):
        self.phase.PreviousPhase=self.other_phase
        self.assertFalse(self.verify()['ok']);self.assertEqual(self.calls,[])
    def test_current_and_parent_state_must_match(self):
        for phase in [self.phase,self.initial]:
            self.soil.Active[phase]=False
            self.assertFalse(self.verify()['ok'])
            self.soil.Active[phase]=True
        self.assertEqual(self.calls,[])
    def test_changed_geometry_or_other_soil_invalidates_permit(self):
        self.assertTrue(self.verify()['ok'])
        self.soil.Parent.BoundingBox.xMax=16
        self.assertFalse(self.change()['ok'])
        self.assertTrue(self.verify()['ok'])
        self.outside.Active[self.phase]=False
        self.assertFalse(self.change()['ok']);self.assertEqual(self.calls,[])
    def test_mutation_between_verification_and_change_invalidates(self):
        self.assertTrue(self.verify()['ok'])
        self.run_rows([{'command':'gotostages'}])
        self.assertFalse(self.change()['ok']);self.assertEqual(self.calls,[])
    def test_curved_tunnel_not_verified_by_box(self):
        with self.assertRaises(RuntimeError):self.verify(shape='tunnel')
        self.assertEqual(self.calls,[])
    def test_missing_third_dimension_rejected(self):
        self.soil.Parent.BoundingBox.zMin=-2;self.soil.Parent.BoundingBox.zMax=0
        self.assertFalse(self.verify()['ok'])
        self.assertTrue(self.verify(region={'x':[10,20],'y':[-5,0],'z':[-2,0]})['ok'])
    def test_unreadable_boolean_is_not_truthy_success(self):
        self.soil.Active[self.phase]='False'
        self.assertFalse(self.verify()['ok']);self.assertEqual(self.calls,[])
    def test_readback_mismatch_stops_remaining_batch(self):
        self.assertTrue(self.verify()['ok'])
        self.g.set=lambda *a:self.calls.append(a)
        result=self.run_rows([{'command':'set','args':[{'ref':'Soil_1.Active'},{'ref':'Phase_1'},False]},
                              {'command':'gotostages'}])
        self.assertFalse(result['ok']);self.assertTrue(result['command_started'])
        self.assertTrue(result['uncertain']);self.assertEqual(len(result['not_run']),1)
        self.assertNotIn('stage_permit',self.session)
    def test_outside_soil_changed_by_api_detected(self):
        self.assertTrue(self.verify()['ok'])
        def bad_set(prop,phase,value):prop[phase]=value;self.outside.Active[phase]=value
        self.g.set=bad_set
        result=self.change()
        self.assertFalse(result['ok']);self.assertIn('khác cũng đổi',result['error'])
    def test_bulk_and_alternative_syntax_do_not_bypass(self):
        rows=[{'command':'activate','args':[{'ref':'Soil_1'},{'ref':'Phase_1'}]},
              {'command':'DEACTIVATE','args':[{'ref':'Soil_1'},{'ref':'Phase_1'}]},
              {'command':'setproperties','args':[{'ref':'Soil_1'},'Active',False]},
              {'command':'set','args':[{'ref':'Soil_1.Active'},False]},
              {'command':'set','args':[{'ref':'Soil_1.Active'},{'ref':'Phase_1'},0]},
              {'command':'set','args':[[{'ref':'Soil_1.Active'},{'ref':'Soil_2.Active'}],{'ref':'Phase_1'},False]},
              {'command':'set','args':[{'ref':'property_alias'},False]}]
        for row in rows:
            with self.subTest(row=row):
                result=self.run_rows([row,{'command':'gotostages'}])
                self.assertFalse(result['ok']);self.assertFalse(result['command_started'])
                self.assertEqual(len(result['not_run']),1)
        self.assertEqual(self.calls,[])
    def test_stop_does_not_send_active_change(self):
        self.assertTrue(self.verify()['ok']);stop_automation()
        self.assertFalse(self.change()['ok']);self.assertEqual(self.calls,[])
    def test_stop_arriving_after_preflight_prevents_write(self):
        from unittest.mock import patch
        from assistant.plaxis_stage_guard import before_change
        self.assertTrue(self.verify()['ok'])
        def preflight(*args):
            checked=before_change(*args)
            stop_automation()
            return checked
        with patch('assistant.plaxis_stage_guard.before_change',side_effect=preflight):
            result=self.change()
        self.assertFalse(result['ok']);self.assertFalse(result['command_started'])
        self.assertEqual(self.calls,[])

    def test_inspect_returns_geometry_and_parent_state_without_permit(self):
        result=self.run_rows([{'command':'inspect_stage','args':[{'ref':'Phase_1'},{'ref':'g.Soils'}]}])
        self.assertTrue(result['ok'],result)
        row=result['results'][0]['value']['objects'][0]
        self.assertEqual(row['bounds']['x'],[10,15]);self.assertTrue(row['parent_active'])
        self.assertNotIn('stage_permit',self.session)
    def test_missing_geometry_does_not_grant(self):
        del self.soil.Parent.BoundingBox
        self.assertFalse(self.verify()['ok']);self.assertNotIn('stage_permit',self.session)
    def test_invalid_region_source_and_numbers(self):
        for changes in [dict(source=''),dict(region={'x':[10,10],'y':[-5,0]}),dict(region={'x':[10,float('nan')],'y':[-5,0]}),dict(before=1)]:
            with self.subTest(changes=changes),self.assertRaises((RuntimeError,ValueError)):
                self.verify(**changes)

if __name__=='__main__':unittest.main()
