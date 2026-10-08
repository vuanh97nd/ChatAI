import math
import tempfile
import unittest
from pathlib import Path
import ezdxf
from assistant.cdm_boundary import layout_in_boundary,add_piles,list_regions

class BoundaryTests(unittest.TestCase):
    def doc(self,pts=((0,0),(12,0),(12,100),(0,100))):
        d=ezdxf.new('R2010');e=d.modelspace().add_lwpolyline(pts,close=True)
        return d,e
    def layout(self,d,e,**kwargs):
        defaults=dict(diameter_m=.8,spacing_x_m=2,spacing_y_m=2,drawing_units='m');defaults.update(kwargs)
        return layout_in_boundary(d,e.dxf.handle,**defaults)
    def test_count_radius_and_boundary_clearance(self):
        d,e=self.doc();r=self.layout(d,e)
        self.assertEqual(len(r['centers']),300)
        self.assertEqual(r['radius'],.4)
        self.assertEqual(min(x for x,y in r['centers']),1)
        self.assertEqual(min(y for x,y in r['centers']),1)
        self.assertTrue(all(.4<=x<=11.6 and .4<=y<=99.6 for x,y in r['centers']))
    def test_actual_units_override_wrong_header(self):
        d,e=self.doc(((0,0),(12000,0),(12000,100000),(0,100000)));d.units=6
        r=self.layout(d,e,drawing_units='mm')
        self.assertEqual(len(r['centers']),300);self.assertEqual(r['radius'],400)
    def test_concave_boundary_excludes_notch(self):
        d,e=self.doc(((0,0),(12,0),(12,10),(6,10),(6,20),(0,20)))
        r=self.layout(d,e)
        self.assertTrue(all(not(x>5.6 and y>9.6) for x,y in r['centers']))
    def test_rotated_large_coordinates(self):
        a=math.radians(30);c,s=math.cos(a),math.sin(a)
        pts=[(800000+c*x-s*y,400000+s*x+c*y) for x,y in ((0,0),(12,0),(12,100),(0,100))]
        d,e=self.doc(pts);r=self.layout(d,e,angle_deg=30)
        self.assertEqual(len(r['centers']),300)
    def test_refuses_unsafe_or_unsupported_regions(self):
        d,e=self.doc(((0,0),(10,10),(0,10),(10,0)))
        with self.assertRaisesRegex(ValueError,'tự giao'):self.layout(d,e)
        d,e=self.doc();e.set_points([(0,0,0,0,1),(12,0,0,0,0),(12,100,0,0,0),(0,100,0,0,0)])
        with self.assertRaisesRegex(ValueError,'bulge'):self.layout(d,e)
        d,e=self.doc()
        with self.assertRaises(ValueError):self.layout(d,e,diameter_m=float('nan'))
        with self.assertRaisesRegex(ValueError,'vị trí thử'):self.layout(d,e,diameter_m=.001,spacing_x_m=.01,spacing_y_m=.01)
    def test_does_not_change_original_entities_or_style(self):
        d,e=self.doc();t=d.modelspace().add_text('Chữ gốc',dxfattribs={'height':1})
        original=[x.dxf.handle for x in d.modelspace()];layer=e.dxf.layer;style=t.dxf.style
        r=self.layout(d,e);name=add_piles(d,r)
        self.assertEqual([x.dxf.handle for x in d.modelspace()][:2],original)
        self.assertEqual(e.dxf.layer,layer);self.assertEqual(t.dxf.style,style)
        self.assertEqual(len(d.modelspace().query('CIRCLE')),300)
        self.assertEqual(list_regions(d)['regions'][0]['handle'],e.dxf.handle)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'copy.dxf';d.saveas(p);restored=ezdxf.readfile(p)
            self.assertEqual(len(restored.audit().errors),0)
            self.assertEqual(len(restored.modelspace().query('CIRCLE')),300)
        self.assertNotEqual(add_piles(d,r),name)
    def test_polyline_prompt_not_routed_to_standalone_drawing(self):
        from assistant.online_automation import cdm_layout_call
        self.assertIsNone(cdm_layout_call('Bố trí CDM trong vùng polyline B=12 L=100 D=0.8 H=17 lưới 2x2',{'windows_apps_enabled':True}))
        from assistant.tools import EXTRA_TOOLS
        names={t['function']['name'] for _,t in EXTRA_TOOLS}
        self.assertTrue({'cad_cdm_regions','cad_cdm_fill_boundary'}<=names)

    def test_source_change_blocks_commit(self):
        from assistant.cdm_layout import CdmLayoutApp
        from assistant.files import FileTools
        class Windows:
            def check(self):return {}
            def allowed_path(self,path):return Path(path)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);d,e=self.doc();source=root/'CDM.dxf';d.saveas(source)
            app=root/'acad.exe';app.write_bytes(b'fake')
            tools=CdmLayoutApp(Windows(),FileTools([root],root/'backup',lambda *a:None),lambda *a:None)
            args=dict(path=str(source),app=str(app),handle=e.dxf.handle,diameter_m=.8,spacing_x_m=2,spacing_y_m=2,drawing_units='m')
            plan=tools.prepare('cad_cdm_fill_boundary',args)
            self.assertEqual(plan['pile_count'],300)
            self.assertNotEqual(plan['path'],str(source))
            source.write_bytes(source.read_bytes()+b'\n')
            with self.assertRaisesRegex(PermissionError,'đã đổi'):tools.commit(plan)
            self.assertFalse(Path(plan['path']).exists())
