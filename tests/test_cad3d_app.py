import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ezdxf
from assistant.cad3d_app import Cad3DApp, build_mesh, shape_from_json
from assistant.files import FileTools


BOX=dict(type='box',origin=[5,10,15],width=10,depth=20,height=30)
CYLINDER=dict(type='cylinder',origin=[0,0,0],radius=50,height=20)
FLANGE=dict(type='flange',origin=[0,0,0],outer_radius=120,inner_radius=40,height=20,hole_radius=9,hole_count=8,bolt_radius=90)


def volume(vertices,faces):
    total=0
    for face in faces:
        a=vertices[face[0]]
        for i in range(1,len(face)-1):
            b,c=vertices[face[i]],vertices[face[i+1]]
            total+=sum(a[k]*(b[(k+1)%3]*c[(k+2)%3]-b[(k+2)%3]*c[(k+1)%3]) for k in range(3))/6
    return total


class Cad3DTest(unittest.TestCase):
    def test_meshes_have_correct_volume_closed_edges_and_through_holes(self):
        for shape,expected,holes in ((BOX,6000,0),(CYLINDER,math.pi*50**2*20,0),
                                    (FLANGE,math.pi*(120**2-40**2-8*9**2)*20,9)):
            with self.subTest(kind=shape['type']):
                vertices,faces=build_mesh(shape_from_json(json.dumps(shape)))
                edges={}
                for face in faces:
                    for a,b in zip(face,face[1:]+face[:1]):
                        key=tuple(sorted((a,b)));edges.setdefault(key,[]).append((a,b))
                self.assertTrue(all(len(e)==2 and e[0]==e[1][::-1] for e in edges.values()))
                self.assertEqual(len(vertices)-len(edges)+len(faces),2-2*holes)
                self.assertAlmostEqual(volume(vertices,faces),expected,delta=expected*.002)

    def test_real_3d_dxf_roundtrip_launch_and_revocation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'acad.exe';app.write_bytes(b'fixture')
            files=FileTools([str(root)],root/'backups',lambda *a:None)
            windows=SimpleNamespace(check=lambda:{},allowed_path=lambda p:Path(p))
            tool=Cad3DApp(windows,files,lambda *a:None)
            plan=tool.prepare('cad3d_create_open',dict(app=str(app),units='mm',shape=json.dumps(FLANGE)))
            with patch('assistant.cad3d_app.subprocess.Popen') as launch:
                result=tool.commit(plan)
                launch.assert_called_once_with([str(app),result['path']],shell=False)
                doc=ezdxf.readfile(result['path']);self.assertEqual(doc.units,4)
                self.assertFalse(doc.audit().has_errors)
                mesh=list(doc.modelspace().query('MESH'))[0]
                vertices=[tuple(v) for v in mesh.vertices];faces=[tuple(f) for f in mesh.faces]
                self.assertEqual(set(v[2] for v in vertices),{0,20})
                self.assertAlmostEqual(volume(vertices,faces),math.pi*(120**2-40**2-8*9**2)*20,delta=2000)
                self.assertEqual(result['representation'],'closed_mesh')
                self.assertEqual(tuple(doc.viewports.get_config('*Active')[0].dxf.direction),(1,-1,1))
                with self.assertRaises(FileExistsError):tool.commit(plan)
                app.write_bytes(b'changed')
                with self.assertRaises(PermissionError):tool.commit(plan)
            windows.check=lambda:(_ for _ in ()).throw(PermissionError('revoked'))
            with self.assertRaises(PermissionError):tool.prepare('cad3d_create_open',dict(app=str(app),units='mm',shape=json.dumps(BOX)))

    def test_invalid_or_overlapping_geometry_and_code_rejected(self):
        invalid=[dict(BOX,width=0),dict(BOX,height=float('nan')),dict(BOX,origin=[0,0]),dict(BOX,command='bad'),
                 dict(FLANGE,hole_radius=40),dict(FLANGE,hole_count=32,hole_radius=15),dict(FLANGE,inner_radius=-1),
                 dict(FLANGE,hole_count=True),dict(type='script',origin=[0,0,0])]
        for shape in invalid:
            with self.subTest(shape=shape),self.assertRaises(ValueError):shape_from_json(json.dumps(shape))

    def test_online_plan_accepts_shape_object_with_tool_schema(self):
        from assistant.tools import EXTRA_TOOLS
        from assistant.online_automation import parse_plan
        schemas=[spec for module,spec in EXTRA_TOOLS if module=='cad3d_app']
        plan=parse_plan(json.dumps({'answer':'','tool':'cad3d_create_open','arguments':{'app':'acad.exe','units':'mm','shape':BOX}}),schemas)
        self.assertEqual(json.loads(plan['arguments']['shape']),BOX)
