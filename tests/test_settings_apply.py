"""Execute actual settings methods with widget doubles; no GUI runtime required."""
import ast
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from assistant import config
from assistant.themes import style_sheet,recolor,chat_style,bubble_color

class Combo:
    def __init__(self,value):self.v=value
    def currentData(self):return self.v
    def findData(self,v):return v
    def currentText(self):return self.v
    def setCurrentText(self,v):self.v=v
    def currentIndex(self):return 0 if self.v=='cloudflare' else 1
    def setCurrentIndex(self,v):self.v=v if isinstance(v,str) else ('cloudflare' if v==0 else 'local')
class Spin:
    def __init__(self,value):self.v=value
    def value(self):return self.v
    def setValue(self,v):self.v=v
class Text:
    def __init__(self,value):self.v=value
    def text(self):return self.v
    def toPlainText(self):return self.v
    def setText(self,v):self.v=v
    def setPlainText(self,v):self.v=v
    def styleSheet(self):return getattr(self,'style','')
    def setStyleSheet(self,v):self.style=v
    def property(self,key):return getattr(self,key,None)
    def setProperty(self,key,v):setattr(self,key,v)
class Check:
    def isChecked(self):return True
    def setChecked(self,value):pass

class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        cfg={'default_model':'qwen2.5:7b','code_model':'qwen2.5-coder:7b','num_ctx':4096,'num_predict':1536,'font_size':16,'max_rounds':8,'temperature':.2,'auto_python':True,'chat_provider':'cloudflare','server_url':'https://server.example','whitelist':['workspace'],'ollama_host':'http://127.0.0.1:11434'}
        (self.root/'config.json').write_text(json.dumps(cfg))
        self.root_patch=patch.object(config,'ROOT',self.root);self.root_patch.start()
        cfg=config.validate_config(cfg)
        source=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        methods=[n for n in window.body if isinstance(n,ast.FunctionDef) and n.name in ('proposed_settings','settings_dirty','discard_settings','save_settings','preview_appearance','apply_theme','apply_font')]
        klass=ast.ClassDef(name='TestWindow',bases=[],keywords=[],body=methods,decorator_list=[])
        namespace={'re':re,'style_sheet':style_sheet,'recolor':recolor,'QWidget':Text,'QComboBox':Combo,'CLOUD_MODEL':'Cloudflare AI','QMessageBox':SimpleNamespace(information=lambda *args:None)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[])),'settings','exec'),namespace)
        self.ui=namespace['TestWindow']();u=self.ui;u.cfg=cfg
        from assistant.storage import Store
        u.store=Store(self.root/'history.db');u.server_session={'username':'test','endpoint':cfg['server_url']}
        u.settings_fields={key:Combo(cfg[key]) if key.endswith('model') else Spin(cfg[key]) for key in ('default_model','code_model','num_ctx','num_predict','font_size','max_rounds','temperature')}
        u.settings_theme=Combo(cfg['theme']);u.preview_theme=cfg['theme'];u.preview_font_size=cfg['font_size'];u.settings_provider=Combo('cloudflare');u.auto_python_check=Check();u.settings_server=Text(cfg['server_url']);u.settings_roots=Text('workspace')
        u.model=Combo('Cloudflare AI');u.status=Text('');u.html_cache={};u.draw=lambda:None;u.render=lambda:None;u.busy=lambda:False
        u.view=Text('');u.colored_widget=Text('');u.colored_widget.setStyleSheet('color:#a8c7fa;background:#282a2c;');u.paint_timer=object()
        u.findChildren=lambda cls:[u.view,u.colored_widget];u.setStyleSheet=lambda css:setattr(u,'stylesheet',css)
        u.work=lambda fn,callback:callback(fn(lambda event:None))

    def tearDown(self):
        self.root_patch.stop();self.temp.cleanup()

    def test_apply_persists_and_updates_without_changing_page(self):
        u=self.ui;self.assertFalse(u.settings_dirty())
        u.settings_fields['num_ctx'].setValue(2048);u.settings_provider.v='local'
        self.assertTrue(u.settings_dirty());u.save_settings()
        payload=json.loads((self.root/'config.json').read_text())
        self.assertEqual(payload['num_ctx'],2048);self.assertEqual(payload['chat_provider'],'local');self.assertNotIn('roots',payload)
        self.assertEqual(u.model.currentText(),'qwen2.5:7b');self.assertFalse(u.settings_dirty());self.assertTrue(list((self.root/'data/backups').glob('config-*')))

    def test_invalid_setting_keeps_original_configuration(self):
        before=(self.root/'config.json').read_bytes();self.ui.settings_fields['num_ctx'].setValue(999999)
        with self.assertRaises(ValueError):self.ui.save_settings()
        self.assertEqual((self.root/'config.json').read_bytes(),before)

    def test_discard_restores_fields_without_writing(self):
        before=(self.root/'config.json').read_bytes();self.ui.settings_fields['font_size'].setValue(20)
        self.ui.discard_settings();self.assertFalse(self.ui.settings_dirty());self.assertEqual((self.root/'config.json').read_bytes(),before)

    def test_theme_preview_does_not_write_and_discard_restores_colors(self):
        u=self.ui;before=(self.root/'config.json').read_bytes()
        u.settings_theme.v='light';u.preview_appearance()
        self.assertEqual(u.cfg['theme'],'dark');self.assertEqual(u.preview_theme,'light')
        self.assertEqual((self.root/'config.json').read_bytes(),before)
        self.assertIn('#1a73e8',u.colored_widget.styleSheet());self.assertTrue(u.settings_dirty())
        u.discard_settings()
        self.assertEqual(u.preview_theme,'dark');self.assertIn('#a8c7fa',u.colored_widget.styleSheet());self.assertFalse(u.settings_dirty())

    def test_saved_theme_restored_by_config_loader(self):
        u=self.ui;u.settings_theme.v='light';u.settings_fields['font_size'].setValue(18);u.preview_appearance();u.save_settings()
        saved=config.load_config()
        self.assertEqual(saved['theme'],'light');self.assertEqual(saved['font_size'],18)
        self.assertEqual(u.preview_font_size,18);self.assertIn('18px',u.view.styleSheet());self.assertFalse(u.settings_dirty())

    def test_invalid_theme_rejected_without_writing(self):
        before=(self.root/'config.json').read_bytes();self.ui.settings_theme.v='invalid'
        with self.assertRaises(ValueError):self.ui.save_settings()
        self.assertEqual((self.root/'config.json').read_bytes(),before)

    def test_markdown_export_cannot_override_chat_font_size(self):
        from assistant.themes import normalize_chat_html
        rendered=normalize_chat_html('<p style="font-size:24pt;color:red;"><span style="font-size:9pt;font-weight:700;">Text</span></p>')
        self.assertNotIn('font-size',rendered)
        self.assertIn('font-weight:700',rendered)
        css=chat_style('dark',16)
        self.assertIn('p, td, li, span {font-size:16px;}',css)
        self.assertIn('h1 {font-size:19px;}',css)

    def test_old_font_restored_once_and_future_choice_retained(self):
        first=config.load_config()
        self.assertEqual(first['font_size'],13)
        self.assertEqual(first['chat_font_revision'],2)
        first['font_size']=15;config.save_config(first)
        self.assertEqual(config.load_config()['font_size'],15)
