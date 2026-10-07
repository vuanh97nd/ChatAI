import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ezdxf
from assistant.cad_app import CadApp, entities_from_json
from assistant.files import FileTools
from assistant.installed_apps import matches_app


class CadTest(unittest.TestCase):
    def test_real_dxf_roundtrip_geometry_units_and_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'acad.exe';app.write_bytes(b'fixture')
            audit=lambda *a:None
            files=FileTools([str(root)],root/'backups',audit)
            windows=SimpleNamespace(check=lambda:{},allowed_path=lambda p:Path(p))
            tool=CadApp(windows,files,audit)
            entities=[{'type':'circle','center':[10,20],'radius':50},
                      {'type':'line','start':[0,0],'end':[100,0]},
                      {'type':'rectangle','origin':[0,0],'width':100,'height':50}]
            plan=tool.prepare('cad_create_open',{'app':str(app),'units':'mm','entities':json.dumps(entities)})
            with patch('assistant.cad_app.subprocess.Popen') as launch:
                result=tool.commit(plan)
                launch.assert_called_once_with([str(app),result['path']],shell=False)
                drawing=ezdxf.readfile(result['path']);self.assertEqual(drawing.units,4)
                self.assertFalse(drawing.audit().has_errors)
                circle=list(drawing.modelspace().query('CIRCLE'))[0]
                self.assertEqual(circle.dxf.radius,50);self.assertEqual(tuple(circle.dxf.center),(10,20,0))
                rectangle=list(drawing.modelspace().query('LWPOLYLINE'))[0]
                self.assertTrue(rectangle.closed);self.assertEqual(len(rectangle),4)
                self.assertEqual(len(drawing.modelspace().query('LINE')),1)
                with self.assertRaises(FileExistsError):tool.commit(plan)
            app.write_bytes(b'changed')
            with self.assertRaises(PermissionError):tool.commit(plan)

    def test_invalid_shapes_and_commands_rejected(self):
        for value in ('[]','[{"type":"command","text":"bad"}]',
                      '[{"type":"circle","center":[0,0],"radius":-1}]',
                      '[{"type":"circle","center":[0,0],"radius":NaN}]',
                      '[{"type":"line","start":[0,0],"end":[0,0]}]'):
            with self.assertRaises(ValueError):entities_from_json(value)

    def test_open_and_draw_prompt_discovers_autocad_without_drawing_words(self):
        from assistant.online_automation import application_call,requested_automation
        call=application_call('mở autocad vẽ cho tôi một đường tròn',{'windows_apps_enabled':True})
        self.assertEqual(call['function']['arguments']['query'],'autocad')
        self.assertTrue(requested_automation('vẽ đường tròn trong AutoCAD'))

    def test_autocad_alias_matches_real_executable(self):
        row={'name':'acad.exe','path':r'C:\\CAD\\acad.exe'}
        self.assertTrue(matches_app(row,'AutoCAD'))
        self.assertFalse(matches_app({'name':'Other','path':r'C:\\Other\\other.exe'},'AutoCAD'))
