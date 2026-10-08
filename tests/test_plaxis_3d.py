import json
import unittest
from types import SimpleNamespace
from assistant.plaxis_app import _generate_script,_validate_problem,_PORT
from assistant.plaxis_remote import _extract_results
from assistant.online_automation import plaxis_call
from tests.test_plaxis_ai import SLOPE_PROBLEM

class Plaxis3DTests(unittest.TestCase):
    def test_longitudinal_dimension_is_required_not_assumed(self):
        problem=_validate_problem(json.dumps({'type':'embankment_stability'}))
        with self.assertRaisesRegex(ValueError,'embankment_length'):
            _generate_script(problem,'3d',10000,'3D')
    def test_3d_geometry_is_volume_and_z_is_vertical(self):
        problem=_validate_problem(json.dumps({'type':'embankment_stability','embankment_length':20}))
        script=_generate_script(problem,'3d',10000,'3D')
        self.assertIn('borehole(0, 0)',script)
        self.assertIn('initializerectangular(0, 0, 50.0, 20.0)',script)
        self.assertIn('g.extrude(emb_surface, 0, 20.0, 0)',script)
        self.assertIn('g.setmaterial(emb_volume.Soil, mat_fill)',script)
        self.assertNotIn('g.polygon(',script)
        self.assertIn('phase2 = g.phase(phase0)',script)
        self.assertEqual(script.count('DeformCalcType = "Safety"'),2)
        self.assertEqual(_PORT['3d'],10000)
    def test_3d_does_not_reuse_2d_slope_script(self):
        with self.assertRaisesRegex(ValueError,'hình học'):
            _generate_script(_validate_problem(SLOPE_PROBLEM),'3d',10000,'Slope')
        self.assertIsNone(plaxis_call('chạy bờ đắp PLAXIS 3D',{'windows_apps_enabled':True},True))
    def test_3d_settlement_reads_uz(self):
        calls=[]
        def results(phase,kind,where):
            calls.append(kind)
            return [-.01] if kind=='Uz' else ([.003] if kind=='Ux' else [.004])
        g=SimpleNamespace(ResultTypes=SimpleNamespace(Soil=SimpleNamespace(Uz='Uz',Ux='Ux',Uy='Uy',MeanEffStress='stress')),getresults=results)
        result=_extract_results(g,[SimpleNamespace(Identification='Drained')],'embankment_stability','3d')
        self.assertEqual(result['max_settlement_mm'],10)
        self.assertIn('Uz',calls)
        self.assertEqual(result['max_horizontal_displacement_mm'],5)
