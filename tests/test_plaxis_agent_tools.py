import json
import unittest
from unittest.mock import Mock
from unittest.mock import patch
from types import SimpleNamespace
from pydantic import ValidationError
from assistant.plaxis_agent.tools import execute, prepare, schemas
from assistant.tools import EXTRA_TOOLS, validate_call
from assistant.communication import method_for


MATERIAL = {'version':'2d','name':'Sand','gamma_unsat':17,'gamma_sat':20,
            'e_ref':13000,'nu':.3,'c':1,'phi':30,'psi':0,'drainage':'Drained','source':'Manual chapter 1 table'}


class SafeToolsTests(unittest.TestCase):
    def setUp(self):
        from assistant.windows_apps import resume_automation
        resume_automation()
    def test_invalid_inputs_never_touch_backend(self):
        for changed in ({'e_ref':float('nan')},{'e_ref':True},{'nu':.5},
                        {'gamma_sat':10},{'psi':40},{'code':'g.exec()'}):
            remote=Mock()
            result=execute(remote,'plaxis_safe_material',{**MATERIAL,**changed})
            self.assertFalse(result['ok']);self.assertTrue(result['not_executed'])
            remote.commit.assert_not_called();remote.prepare.assert_not_called()

    def test_material_commands_are_generated_and_units_checked(self):
        remote=Mock();remote.commit.return_value={'ok':True}
        self.assertTrue(execute(remote,'plaxis_safe_material',MATERIAL)['ok'])
        name,args=remote.prepare.call_args.args
        self.assertEqual(name,'plaxis_commands')
        rows=json.loads(args['commands'])
        self.assertEqual(rows[1]['command'],'verify_model')
        self.assertIn('UnitForce',rows[1]['args'][0])
        self.assertEqual(rows[2]['command'],'ensure_new_material')
        self.assertEqual(rows[3]['command'],'soilmat')
        self.assertNotIn('exec',[row['command'] for row in rows])

    def test_layer_schema_requires_2d_and_positive_thickness(self):
        for data in ({'version':'3d','thickness':1,'source':'test'},
                     {'version':'2d','thickness':0,'source':'test'}):
            with self.assertRaises(ValidationError):prepare('plaxis_safe_layer',data)

    def test_calculate_cannot_accept_arbitrary_reference(self):
        for ref in ('g.__class__','g.Soils[0]','g.Project.Delete'):
            with self.assertRaises(ValidationError):
                prepare('plaxis_safe_calculate',{'version':'2d','checks':[{'ref':ref,'expected':0}],'source':'test'})

    def test_desktop_registry_validates_pydantic_nested_checks(self):
        registry=[schema for _,schema in EXTRA_TOOLS]
        args={'version':'2d','checks':[{'ref':'g.Project.ModelType','expected':0}],'source':'test'}
        validate_call('plaxis_safe_calculate',args,registry)
        with self.assertRaises(ValidationError):validate_call('plaxis_safe_calculate',{**args,'checks':[]},registry)
        self.assertEqual(method_for('plaxis_safe_material'),'application_api')
        self.assertEqual(len(schemas()),4)

    def test_failure_is_not_retried(self):
        remote=Mock();remote.commit.side_effect=RuntimeError('native connection lost')
        with self.assertLogs('chatai.plaxis_agent',level='ERROR'):
            result=execute(remote,'plaxis_safe_inspect',{'version':'2d'})
        self.assertFalse(result['ok']);self.assertTrue(result['uncertain'])
        self.assertEqual(remote.commit.call_count,1)

    def test_real_wrapper_route_keeps_two_materials_separate_and_rejects_duplicate(self):
        from assistant.plaxis_remote import PlaxisRemoteApp
        g=SimpleNamespace(Project=SimpleNamespace(UnitLength='m',UnitForce='kN'),Materials=[],Soils=[],gotosoil=Mock())
        def create():
            material=SimpleNamespace(Identification='Unnamed')
            g.Materials.append(material)
            return material
        def setproperties(material,*args):
            for key,value in zip(args[::2],args[1::2]):setattr(material,key,value)
            return 'OK'
        g.soilmat=Mock(side_effect=create);g.setproperties=Mock(side_effect=setproperties)
        remote=PlaxisRemoteApp(None)
        with patch('assistant.plaxis_remote.resolve_port',return_value=(19876,True)),patch('assistant.plaxis_remote._connect',return_value=(Mock(),g)):
            for data in (MATERIAL,{**MATERIAL,'name':'Clay','phi':20}):
                result=remote.commit(remote.prepare('plaxis_safe_material',data))
                self.assertTrue(result['ok'],result)
                self.assertTrue(result['material_verified'])
                self.assertFalse(result['model_verified'])
            result=remote.commit(remote.prepare('plaxis_safe_material',MATERIAL))
        self.assertFalse(result['ok'])
        self.assertEqual([material.Identification for material in g.Materials],['Sand','Clay'])
        self.assertEqual([material.phi for material in g.Materials],[30,20])
        self.assertEqual(g.soilmat.call_count,2)
