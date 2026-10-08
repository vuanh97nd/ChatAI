import json
import unittest
from types import SimpleNamespace
from assistant.plaxis_app import _stratigraphy_lines,_generate_script,_validate_problem
from tests.test_plaxis_ai import FOUNDATION_PROBLEM,SLOPE_PROBLEM,RETAINING_PROBLEM,EXCAVATION_PROBLEM

class SoilGeometry:
    def __init__(self):self.Soillayers=[];self.thickness=[];self.mode=None;self.boreholes=0
    def gotosoil(self):self.mode='soil'
    def gotostructures(self):self.mode='structures'
    def borehole(self,*args):
        assert self.mode=='soil';self.boreholes+=1;return SimpleNamespace(Head=None)
    def soillayer(self,thickness):
        assert self.mode=='soil' and thickness>0
        self.thickness.append(thickness);self.Soillayers.append(SimpleNamespace(Soil=SimpleNamespace(material=None)))
    def setmaterial(self,soil,material):soil.material=material

class StratigraphyTests(unittest.TestCase):
    def test_layers_have_requested_thickness_and_matching_material(self):
        for version in ('2d','3d'):
            g=SoilGeometry();materials=[object(),object()]
            exec(_stratigraphy_lines([{'thickness':4.0},{'thickness':6.0}],version),{'g':g,'soil1':materials[0],'soil2':materials[1]})
            self.assertEqual(g.thickness,[4.0,6.0]);self.assertEqual(g.boreholes,1)
            self.assertEqual([s.Soil.material for s in g.Soillayers],materials)
            self.assertEqual(g.mode,'structures')
    def test_every_model_assigns_soil_before_mesh_and_calculation(self):
        for source in [FOUNDATION_PROBLEM,SLOPE_PROBLEM,RETAINING_PROBLEM,EXCAVATION_PROBLEM,json.dumps({'type':'embankment_stability'})]:
            problem=_validate_problem(source);script=_generate_script(problem,'2d',10000,'Test')
            with self.subTest(problem=problem['type']):
                self.assertNotIn('g.soillayer(0)',script)
                self.assertLess(script.index('g.setmaterial(g.Soillayers[0].Soil'),script.index('g.gotomesh()'))
                if 'soil_layers' in problem:
                    for i,layer in enumerate(problem['soil_layers']):
                        self.assertIn(f'g.setmaterial(g.Soillayers[{i}].Soil, soil{i+1})',script)

    def test_embankment_uses_polygon_command_and_assigns_returned_soil(self):
        script=_generate_script(_validate_problem(json.dumps({'type':'embankment_stability'})),'2d',10000,'Test')
        self.assertNotIn('g.soilpolygon(',script)
        line=next(line for line in script.splitlines() if line.startswith('emb_polygon, emb ='))
        soil=SimpleNamespace(material=None)
        class Geometry:
            def polygon(self,*points):
                self.points=points
                return object(),soil
            def setmaterial(self,target,material):
                self.assert_target=target
                target.material=material
        g=Geometry();material=object()
        exec(line+'\ng.setmaterial(emb, mat_fill)',{'g':g,'mat_fill':material})
        self.assertEqual(len(g.points),4)
        self.assertIs(g.assert_target,soil)
        self.assertIs(soil.material,material)
        self.assertLess(script.index(line),script.index('g.gotomesh()'))

    def test_embankment_stages_use_polygon_not_geometry_soil_reference(self):
        script=_generate_script(_validate_problem(json.dumps({'type':'embankment_stability'})),'2d',10000,'Test')
        polygon=object();obsolete_soil=object();phases=[object(),object(),object()]
        calls=[]
        class Stages:
            def deactivate(self,target,phase):
                if target is not polygon:raise RuntimeError('Unknown object')
                calls.append(('deactivate',phase))
            def activate(self,target,phase):
                if target is not polygon:raise RuntimeError('Unknown object')
                calls.append(('activate',phase))
        lines=[line for line in script.splitlines() if line.startswith(('g.activate(emb','g.deactivate(emb'))]
        self.assertEqual(len(lines),3)
        exec('\n'.join(lines),{'g':Stages(),'emb_polygon':polygon,'emb':obsolete_soil,
                               'phase0':phases[0],'phase1':phases[1],'phase2':phases[2]})
        self.assertEqual(calls,[('deactivate',phases[0]),('activate',phases[1]),('activate',phases[2])])

    def test_undrained_assignment_resolves_all_staged_clay_clusters(self):
        script=_generate_script(_validate_problem(json.dumps({'type':'embankment_stability'})),'2d',10000,'Test')
        staged=script.split('g.gotostages()',1)[1]
        self.assertNotIn('Soillayers',staged)
        initial=object();undrained=object()
        clay=SimpleNamespace(Identification='SetDrained')
        fill=SimpleNamespace(Identification='BoDapCat')
        soils=[SimpleNamespace(Material={initial:material}) for material in (fill,clay,clay)]
        calls=[]
        g=SimpleNamespace(Soils=soils,setmaterial=lambda *args:calls.append(args))
        block=staged[staged.index('clay_clusters ='):staged.index('# Giai đoạn 3:')]
        exec(block,{'g':g,'phase0':initial,'phase2':undrained,'mat_clay_dr':clay,'mat_clay_ud':'UD'})
        self.assertEqual(calls,[(soils[1],undrained,'UD'),(soils[2],undrained,'UD')])
        with self.assertRaisesRegex(RuntimeError,'Khong tim thay'):
            exec(block,{'g':SimpleNamespace(Soils=[soils[0]]),'phase0':initial,'phase2':undrained,'mat_clay_dr':clay,'mat_clay_ud':'UD'})
