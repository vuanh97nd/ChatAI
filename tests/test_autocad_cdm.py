import tempfile
import unittest
import json
import subprocess
import sys
from pathlib import Path

import ezdxf
from assistant.autocad_cdm import build, render


class AutoCadCdmTests(unittest.TestCase):
    def layout(self):
        return {'action': 'cdm_layout', 'parameters': dict(units='m', b_road=10,
            l_treatment=20, d_pile=0.8, pile_depth=12, spacing_x=1.5, spacing_y=1.5)}

    def profile(self):
        return {'action': 'cdm_profile', 'parameters': {'units': 'm', 'vertical_scale': 5,
            'points': [dict(station=0, ground_elev=2, design_elev=4, pile_top_elev=3, pile_depth=10),
                       dict(station=100, ground_elev=3, design_elev=5, pile_top_elev=4, pile_depth=12)]}}

    def test_rectangular_piles_stay_inside_and_count_matches(self):
        doc, result = build(self.layout())
        circles = list(doc.modelspace().query('CIRCLE'))
        self.assertEqual(len(circles), result['pile_count'])
        boundary = next(e for e in doc.modelspace().query('LWPOLYLINE[layer=="ROAD"]')
                        if min(v[0] for v in e.get_points()) > 5)
        xy = list(boundary.get_points('xy'))
        for circle in circles:
            x, y, _ = circle.dxf.center
            r = circle.dxf.radius
            self.assertAlmostEqual(r, 0.4)
            self.assertGreaterEqual(x-r, min(p[0] for p in xy)-1e-8)
            self.assertLessEqual(x+r, max(p[0] for p in xy)+1e-8)
            self.assertGreaterEqual(y-r, min(p[1] for p in xy)-1e-8)
            self.assertLessEqual(y+r, max(p[1] for p in xy)+1e-8)

    def test_profile_uses_explicit_top_and_depth_with_vertical_scale(self):
        doc, result = build(self.profile())
        msp = doc.modelspace()
        ground = list(next(iter(msp.query('LWPOLYLINE[layer=="KS-TUY-2401-Trắc dọc tự nhiên"]'))).get_points('xy'))
        top = list(next(iter(msp.query('LWPOLYLINE[layer=="CDM-TOP"]'))).get_points('xy'))
        toe = list(next(iter(msp.query('LWPOLYLINE[layer=="CDM-TOE"]'))).get_points('xy'))
        self.assertEqual(result['point_count'], 2)
        self.assertAlmostEqual(top[0][1]-ground[0][1], 5)
        self.assertAlmostEqual(top[0][1]-toe[0][1], 50)
        self.assertAlmostEqual(top[1][1]-toe[1][1], 60)

    def test_exclusive_output_and_dxf_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'test.dxf'
            result = render(self.layout(), str(output))
            self.assertTrue(result['ok'])
            self.assertEqual(ezdxf.readfile(output).units, 6)
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                render(self.profile(), str(output))
            self.assertEqual(output.read_bytes(), before)

    def test_missing_depth_unsorted_and_nonfinite_rejected(self):
        plan = self.profile()
        del plan['parameters']['points'][0]['pile_depth']
        with self.assertRaises(ValueError): build(plan)
        plan = self.profile()
        plan['parameters']['points'][1]['station'] = 0
        with self.assertRaises(ValueError): build(plan)
        plan = self.layout()
        plan['parameters']['d_pile'] = float('nan')
        with self.assertRaises(ValueError): build(plan)

    def test_limits_and_unknown_instructions_rejected(self):
        plan = self.layout()
        plan['parameters']['spacing_x'] = True
        with self.assertRaises(ValueError): build(plan)
        plan = self.layout()
        plan['parameters'].update(b_road=1000, l_treatment=1000)
        with self.assertRaises(ValueError): build(plan)
        plan = self.layout()
        plan['output'] = 'untrusted.dxf'
        with self.assertRaises(ValueError): build(plan)
        with self.assertRaises(ValueError): build({'action': 'shell', 'parameters': {}})

    def test_cli_utf8_request_and_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'mặt bằng.dxf'
            request = json.dumps({'plan': self.layout(), 'output': str(output)}, ensure_ascii=False).encode('utf-8')
            process = subprocess.run([sys.executable, '-m', 'assistant.autocad_cdm'],
                                     input=request, capture_output=True, timeout=30, check=True)
            response = json.loads(process.stdout.decode('utf-8'))
            self.assertTrue(response['ok'])
            self.assertEqual(response['path'], str(output.resolve()))
            self.assertGreater(len(ezdxf.readfile(output).modelspace()), 0)

    def test_selected_concave_boundary_keeps_units_and_excludes_cutout(self):
        plan={'action':'cdm_boundary','parameters':dict(units='mm',
            boundary=[[0,0],[10000,0],[10000,5000],[5000,5000],[5000,10000],[0,10000]],
            d_pile=0.8,spacing_x=1.5,spacing_y=1.5,edge_clearance=0.2,angle_deg=0)}
        doc,result=build(plan)
        self.assertEqual(doc.units,4)
        circles=list(doc.modelspace().query('CIRCLE'))
        self.assertEqual(len(circles),result['pile_count'])
        self.assertGreater(len(circles),0)
        for c in circles:
            self.assertAlmostEqual(c.dxf.radius,400)
            self.assertFalse(c.dxf.center.x>5000 and c.dxf.center.y>5000)

    def test_boundary_rejects_crossing_and_missing_selection(self):
        p=dict(units='m',boundary=[[0,0],[10,10],[0,10],[10,0]],
               d_pile=0.8,spacing_x=1.5,spacing_y=1.5,edge_clearance=0,angle_deg=0)
        with self.assertRaises(ValueError):build({'action':'cdm_boundary','parameters':p})
        del p['boundary']
        with self.assertRaises(ValueError):build({'action':'cdm_boundary','parameters':p})


if __name__ == '__main__':
    unittest.main()
