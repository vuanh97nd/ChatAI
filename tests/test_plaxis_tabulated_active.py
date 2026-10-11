import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
from assistant.plaxis_stage_guard import active,StageGuardError,check_spec
from assistant.plaxis_progress import wall_interfaces
from assistant.windows_apps import resume_automation


class TabulatedActiveTests(unittest.TestCase):
    def setUp(self):resume_automation()
    def test_calculation_uses_live_phase_differences_with_empty_session_log(self):
        from assistant.plaxis_commands import execute_commands
        from tests.test_plaxis_stage_guard import StageGuardTest
        fixture=StageGuardTest();fixture.setUp()
        class Opaque(dict):
            def __getitem__(self,key):raise AttributeError('phase proxy unreadable')
        try:
            fixture.soil.Active=Opaque({fixture.initial:True,fixture.phase:False})
            fixture.outside.Active=Opaque({fixture.initial:True,fixture.phase:True})
            fixture.phase.DeformCalcType=4;fixture.phase.ShouldCalculate=True
            fixture.g.Phases=[fixture.initial,fixture.phase]
            fixture.g.calculate=Mock(return_value='calculated')
            def table(obj,phase,field=None):
                return 'Object\tActive\n'+phase.Name+"'\t"+str(dict.__getitem__(obj.Active,phase))
            fixture.g.tabulate=table
            result=execute_commands(Mock(),fixture.g,[{'command':'calculate','args':[]}],session=fixture.session)
            self.assertTrue(result['ok'],result)
            fixture.g.calculate.assert_called_once_with()
        finally:fixture.tearDown()
    def test_native_cutobject_text_bounds_and_region_guard(self):
        from assistant.plaxis_stage_guard import bounds,textual_bounds
        from tests.test_plaxis_stage_guard import StageGuardTest
        for raw,expected in (
            ('min: (40.00; 27.00; 0.00) max: (40.00; 30.00; 0.00)',{'x':[40,40],'y':[27,30],'z':[0,0]}),
            ('min: (0.00; 27.00; 0.00) max: (40.00; 30.00; 0.00)',{'x':[0,40],'y':[27,30],'z':[0,0]}),
            ('min: (-1e1; -5) max: (2.0E1; 0)',{'x':[-10,20],'y':[-5,0]})):
            self.assertEqual(bounds(NS(Parent=NS(BoundingBox=NS(value=raw)))),expected)
        for raw in ('min: (nan; 0) max: (1; 2)',
                    'min: (0; 0) max: (1; 2; 3)',
                    'min: (2; 0) max: (1; 2)',
                    'min: (0; 0) max: (1e999; 2)',
                    'min: (0; 0) max: (1; 2) trailing'):
            with self.assertRaises(StageGuardError):textual_bounds(raw)
        fixture=StageGuardTest();fixture.setUp()
        try:
            fixture.soil.Parent.BoundingBox='min: (10; -5; 0) max: (15; 0; 0)'
            self.assertTrue(fixture.verify()['ok'])
            self.assertTrue(fixture.change()['ok'])
            fixture.soil.Parent.BoundingBox='min: (0; -5; 0) max: (15; 0; 0)'
            self.assertFalse(fixture.verify()['ok'])
            self.assertEqual(len(fixture.calls),1)
        finally:fixture.tearDown()
    def test_geometry_bounds_follow_parent_and_linked_points(self):
        from assistant.plaxis_stage_guard import bounds
        vertices=[NS(x=40,y=14),NS(x=40,y=30)]
        geometry=NS(Points=vertices)
        self.assertEqual(bounds(NS(Parent=NS(Parent=geometry))),{'x':[40,40],'y':[14,30]})
        self.assertEqual(bounds(NS(Parent=NS(First=vertices[0],Second=vertices[1]))),{'x':[40,40],'y':[14,30]})
        self.assertEqual(bounds(NS(Parent=NS(BoundingBox=NS(XMin=0,XMax=10,YMin=0,YMax=30)))),{'x':[0,10],'y':[0,30]})
        with self.assertRaises(StageGuardError):bounds(NS(Parent=NS(BoundingBox=[0,0,10,30])))
        vertices[1].z=2
        with self.assertRaises(StageGuardError):bounds(NS(Parent=geometry))
    def test_missing_cut_geometry_reports_actual_parent_schema(self):
        from assistant.plaxis_stage_guard import bounds
        parent=NS(Name='Line_1_1')
        g=NS(info=Mock(return_value='Attributes: EndpointA, EndpointB'),commands=Mock(return_value='info, commands'))
        with self.assertRaisesRegex(StageGuardError,'EndpointA, EndpointB'):
            bounds(NS(Parent=parent),g)
        g.info.assert_called_once_with(parent)
        g.commands.assert_called_once_with(parent)
    def test_phase_rows_select_requested_phase_and_reject_ambiguity(self):
        from assistant.plaxis_active import tabulated_active
        obj=NS();phase=NS()
        for separator in ('\t',' '):
            table=separator.join(('Object','Active'))+'\n'+separator.join(('InitialPhase','True'))+'\n'+separator.join(("Phase_1'",'False'))
            g=NS(tabulate=Mock(return_value=table))
            self.assertIs(tabulated_active(g,obj,phase,'Soil_1_1','Phase_1'),False)
            self.assertEqual(g.tabulate.call_count,1)
        for table in ('Object\tActive\nInitialPhase\tTrue\nPhase_2\tFalse',
                      "Object\tActive\nPhase_1\tTrue\nPhase_1'\tFalse",
                      "Object\tActive\nPhase_1'\tNone"):
            with self.assertRaises(ValueError):
                tabulated_active(NS(tabulate=Mock(return_value=table)),obj,phase,'Soil_1_1','Phase_1')
    def test_native_whitespace_quotes_and_named_object_column(self):
        from assistant.plaxis_active import tabulated_active
        obj=NS();phase=NS()
        for table in ('Object Active\nSoil_1_1 False',
                      'Object\tActive\n"Soil_1_1"\tFalse',
                      'Active\tObject\nFalse\tSoil_1_1'):
            self.assertIs(tabulated_active(NS(tabulate=Mock(return_value=table)),obj,phase,'Soil_1_1','Phase_1'),False)
        table='Object\tActive\nSoil_2_1\tFalse'
        with self.assertRaisesRegex(ValueError,'Bảng thô.*Soil_2_1'):
            tabulated_active(NS(tabulate=Mock(return_value=table)),obj,phase,'Soil_1_1','Phase_1')
    def test_none_recovers_only_from_correct_named_phase_boolean(self):
        obj=NS(Name='Plate_1_1',Active={'phase':NS(value=None)})
        phase=NS(Name='Phase_1')
        obj.Active={}
        class Empty:
            def __getitem__(self,key):return NS(value=None)
        obj.Active=Empty()
        g=NS(tabulate=Mock(return_value='Object\tActive[InitialPhase]\tActive[Phase_1]\nPlate_1_1\tTrue\tFalse'))
        self.assertIs(active(obj,phase,g),False)
        g.tabulate.assert_called_once_with(obj,phase,'Active')
        g.tabulate=Mock(return_value='Object\tActive\nPlate_1_1\tFalse')
        self.assertIs(active(obj,phase,g),False)
        g.tabulate.assert_called_once_with(obj,phase,'Active')
        for table in ('Object\tActive[Phase_2]\nPlate_1_1\tFalse',
                      'Object\tActive[Phase_1]\nOther\tFalse',
                      'Object\tActive[Phase_1]\nPlate_1_1\t0',
                      'Object\tActive[Phase_1]\nPlate_1_1\tNone'):
            g.tabulate=Mock(return_value=table)
            with self.assertRaises(StageGuardError):active(obj,phase,g)
            self.assertEqual(g.tabulate.call_count,2)

    def test_guard_can_verify_write_and_readback_with_tabulate_without_bypass(self):
        from tests.test_plaxis_stage_guard import StageGuardTest
        fixture=StageGuardTest();fixture.setUp()
        class Opaque(dict):
            def __getitem__(self,key):return None
        fixture.soil.Active=Opaque(fixture.soil.Active)
        fixture.outside.Active=Opaque(fixture.outside.Active)
        def table(obj,phase,field=None):
            self.assertIn(phase,(fixture.initial,fixture.phase,fixture.other_phase))
            phases=[fixture.initial,fixture.phase,fixture.other_phase]
            header='Object\t'+'\t'.join('Active['+p.Name+']' for p in phases)
            row=obj.Name+'\t'+'\t'.join(str(dict.__getitem__(obj.Active,p)) for p in phases)
            return header+'\n'+row
        fixture.g.tabulate=table
        try:
            self.assertTrue(fixture.verify()['ok'])
            changed=fixture.change()
            self.assertTrue(changed['ok'],changed)
            self.assertIs(changed['results'][0]['readback'],False)
            self.assertNotIn('readback_warning',changed['results'][0])
            self.assertEqual(len(fixture.calls),1)
            self.assertIs(dict.__getitem__(fixture.soil.Active,fixture.phase),False)
            self.assertIs(dict.__getitem__(fixture.outside.Active,fixture.phase),True)
        finally:fixture.tearDown()

    def test_native_phase_argument_precedes_optional_property_and_has_no_unscoped_retry(self):
        from assistant.plaxis_active import tabulated_active
        obj=NS(Name='Soil_1_1');phase=NS(Name='Phase_1')
        def native(target,selected_phase,*fields):
            if selected_phase is not phase:raise RuntimeError('Invalid parameters')
            if not fields:raise RuntimeError('Property required')
            self.assertEqual(fields,('Active',))
            return 'Object\tActive\nSoil_1_1\tTrue'
        g=NS(tabulate=Mock(side_effect=native))
        self.assertIs(tabulated_active(g,obj,phase,'Soil_1_1','Phase_1'),True)
        self.assertEqual(g.tabulate.call_count,1)
        self.assertEqual(g.tabulate.call_args_list[0].args,(obj,phase,'Active'))

    def test_wall_links_find_missing_side_without_confusing_unrelated_interfaces(self):
        g=NS(Plates=[NS(Name='Plate_1',Parent='wall1'),NS(Name='Plate_2',Parent='wall2')],
             Interfaces=[NS(Name='PositiveInterface_1',Parent='wall1'),
                         NS(Name='NegativeInterface_1',Parent='wall1'),
                         NS(Name='PositiveInterface_2',Parent='wall2'),
                         NS(Name='NegativeInterface_3',Parent='unrelated')])
        rows=wall_interfaces(g)['walls']
        self.assertEqual(rows[0]['status'],'present')
        self.assertEqual(rows[1]['missing_sides'],['negative'])
        g.Interfaces.append(NS(Name='RenamedInterface',Parent='unknown'))
        self.assertEqual(wall_interfaces(g)['walls'][1]['status'],'unreadable')

    def test_line_region_for_interface_is_valid_but_zero_width_soil_is_not(self):
        import json
        spec={'target':'NegativeInterface_1','phase':'Phase_1','parent_phase':'InitialPhase',
              'before':False,'parent_active':False,'after':True,'shape':'box',
              'region':{'x':[40,40],'y':[14,30]},'source':'Manual','kind':'interface'}
        self.assertEqual(check_spec(json.dumps(spec))['kind'],'interface')
        spec['kind']='soil'
        with self.assertRaises(StageGuardError):check_spec(json.dumps(spec))
