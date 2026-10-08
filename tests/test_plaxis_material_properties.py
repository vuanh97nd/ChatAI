"""Regression: generated materials must use PLAXIS Identification, not MaterialName."""
import ast
import json
import unittest
from assistant.plaxis_app import _generate_script,_validate_problem
from tests.test_plaxis_ai import FOUNDATION_PROBLEM,SLOPE_PROBLEM,RETAINING_PROBLEM,EXCAVATION_PROBLEM

class MaterialPropertiesTests(unittest.TestCase):
    def test_all_generated_materials_use_supported_name_property(self):
        problems=[FOUNDATION_PROBLEM,SLOPE_PROBLEM,RETAINING_PROBLEM,EXCAVATION_PROBLEM,
                  json.dumps({'type':'embankment_stability'})]
        for version in ('2d','3d'):
            for source in problems:
                with self.subTest(version=version,problem=json.loads(source)['type']):
                    problem=_validate_problem(source)
                    script=_generate_script(problem,version,10000,'Test')
                    tree=ast.parse(script)
                    mats=set();named=set()
                    for node in ast.walk(tree):
                        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr in ('soilmat','platemat'):
                            mats.update(t.id for t in node.targets if isinstance(t,ast.Name))
                        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='setproperties' and node.args:
                            prop=node.args[0]
                            if isinstance(prop,ast.Constant):
                                self.assertNotEqual(prop.value,'MaterialName')
                                if prop.value=='Identification':named.add(node.func.value.id)
                    self.assertTrue(mats)
                    self.assertEqual(mats,named)
