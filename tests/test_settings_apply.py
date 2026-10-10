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
from assistant.cloud import PROVIDER_NAMES, REMOTE_MODELS
from assistant.admin_ui import admin_session
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
    def clear(self):self.v=''
    def styleSheet(self):return getattr(self,'style','')
    def setStyleSheet(self,v):self.style=v
    def property(self,key):return getattr(self,key,None)
    def setProperty(self,key,v):setattr(self,key,v)
class Check:
    def __init__(self,value=True):self.v=value
    def isChecked(self):return self.v
    def setChecked(self,value):self.v=value

class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        cfg={'default_model':'qwen2.5:7b','code_model':'qwen2.5-coder:7b','num_ctx':4096,'num_predict':1536,'font_size':16,'max_rounds':8,'temperature':.2,'machine_auto_ai':False,'auto_python':True,'chat_provider':'cloudflare','server_url':'https://server.example','whitelist':['workspace'],'ollama_host':'http://127.0.0.1:11434'}
        (self.root/'config.json').write_text(json.dumps(cfg))
        self.root_patch=patch.object(config,'ROOT',self.root);self.root_patch.start()
        cfg=config.validate_config(cfg)
        source=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        methods=[n for n in window.body if isinstance(n,ast.FunctionDef) and n.name in ('apply_machine_choices','proposed_settings','settings_dirty','discard_settings','save_settings','preview_appearance','apply_theme','apply_font')]
        klass=ast.ClassDef(name='TestWindow',bases=[],keywords=[],body=methods,decorator_list=[])
        namespace={'PROVIDER_NAMES':PROVIDER_NAMES,'REMOTE_MODELS':REMOTE_MODELS,'admin_session':admin_session,'re':re,'style_sheet':style_sheet,'recolor':recolor,'QWidget':Text,'QComboBox':Combo,'CLOUD_MODEL':'Cloudflare AI','QMessageBox':SimpleNamespace(information=lambda *args:None)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[])),'settings','exec'),namespace)
        self.ui=namespace['TestWindow']();u=self.ui;u.cfg=cfg
        u.isVisible=lambda:False # Settings doubles represent a window before show; visible transitions have Qt paint tests.
        from assistant.storage import Store
        u.store=Store(self.root/'history.db');u.server_session={'username':'test','endpoint':cfg['server_url']}
        u.settings_fields={key:Combo(cfg[key]) if key.endswith('model') else Spin(cfg[key]) for key in ('default_model','code_model','num_ctx','num_predict','font_size','max_rounds','temperature')}
        u.settings_theme=Combo(cfg['theme']);u.preview_theme=cfg['theme'];u.preview_font_size=cfg['font_size'];u.settings_provider=Combo(PROVIDER_NAMES[cfg['chat_provider']]);u.auto_python_check=Check();u.settings_server=Text(cfg['server_url']);u.settings_roots=Text('workspace')
        u.windows_apps_check=Check(cfg['windows_apps_enabled']);u.windows_apps_paths=Text('\n'.join(cfg['windows_apps_allowed']))
        u.browser_background_check=Check(cfg['browser_background'])
        u.windows_compact_check=Check(cfg.get('windows_apps_compact',True))
        u.windows_auto_execute_check=Check(cfg.get('windows_apps_auto_execute',False))
        u.automation_auto_install_check=Check(cfg['automation_auto_install'])
        u.windows_all_apps_check=Check(cfg['windows_apps_all_installed'])
        u.machine_profile=Combo(cfg['machine_profile']);u.machine_auto=Check(cfg['machine_auto_ai']);u.api_model_fields={};u.api_key_fields={}
        u.select_ai=lambda model:u.model.setCurrentText(model)
        u.model=Combo('Cloudflare AI');u.status=Text('');u.html_cache={};u.draw=lambda:None;u.render=lambda:None;u.busy=lambda:False
        u.view=Text('');u.colored_widget=Text('');u.colored_widget.setStyleSheet('color:#a8c7fa;background:#282a2c;');u.paint_timer=object()
        u.findChildren=lambda cls:[u.view,u.colored_widget];u.setStyleSheet=lambda css:setattr(u,'stylesheet',css)
        u.work=lambda fn,callback:callback(fn(lambda event:None))

    def tearDown(self):
        self.root_patch.stop();self.temp.cleanup()

    def test_local_machine_choices_preserve_online_settings(self):
        u=self.ui
        u.settings_fields['api_num_predict']=Spin(3072)
        u.settings_fields['api_temperature']=Spin(.1)
        u.hardware_info={};u.machine_auto.setChecked(True);u.machine_profile.v='weak'
        u.save_settings()
        saved=json.loads((self.root/'config.json').read_text())
        self.assertEqual(saved['api_num_predict'],3072)
        self.assertEqual(saved['api_temperature'],.1)
        self.assertNotEqual(saved['num_predict'],3072)

    def test_blank_optional_provider_model_does_not_block_leaving_settings(self):
        u=self.ui
        u.api_model_fields={'groq':Text('')}
        self.assertNotIn('groq_model',u.cfg)
        self.assertFalse(u.settings_dirty())

    def test_creativity_save_does_not_send_blank_or_unchanged_provider_models(self):
        u=self.ui;u.server_session['username']='admin';u.server_session['role']='system';u.server_session['key']='test-session'
        u.api_model_fields={'deepseek':Text(u.cfg['deepseek_model']),'groq':Text('')}
        u.settings_fields['api_temperature']=Spin(.5)
        with patch('assistant.accounts.request_account') as request:
            u.save_settings()
        request.assert_not_called()
        self.assertEqual(json.loads((self.root/'config.json').read_text())['api_temperature'],.5)
        self.assertEqual(u.status.text(),'Đã lưu cài đặt.')

    def test_provider_edit_sends_only_nonempty_changed_model(self):
        u=self.ui;u.server_session['username']='admin';u.server_session['role']='system';u.server_session['key']='test-session'
        u.api_model_fields={'deepseek':Text('deepseek-v4-pro'),'groq':Text('')}
        with patch('assistant.accounts.request_account') as request:
            u.save_settings()
        self.assertEqual(request.call_args.args[2]['models'],{'deepseek':'deepseek-v4-pro'})

    def test_apply_persists_and_updates_without_changing_page(self):
        u=self.ui;self.assertFalse(u.settings_dirty())
        u.settings_fields['num_ctx'].setValue(2048);u.settings_provider.v='local'
        self.assertTrue(u.settings_dirty());u.save_settings()
        payload=json.loads((self.root/'config.json').read_text())
        self.assertEqual(payload['num_ctx'],2048);self.assertEqual(payload['chat_provider'],'local');self.assertNotIn('roots',payload)
        self.assertEqual(u.model.currentText(),'qwen2.5:7b');self.assertFalse(u.settings_dirty());self.assertTrue(list((self.root/'data/backups').glob('config-*')))

    def test_remembered_app_permission_survives_reload_and_preserves_settings(self):
        saved=config.load_config();saved['windows_apps_enabled']=True
        config.save_config(saved)
        granted=config.remember_app_permission()
        self.assertTrue(granted['windows_apps_auto_execute'])
        reloaded=config.load_config()
        self.assertTrue(reloaded['windows_apps_auto_execute'])
        self.assertEqual(reloaded['server_url'],saved['server_url'])
        reloaded['windows_apps_enabled']=False;config.save_config(reloaded)
        with self.assertRaises(PermissionError):config.remember_app_permission()

    def test_windows_app_permissions_save_and_discard(self):
        u=self.ui
        u.windows_apps_check.setChecked(True)
        u.browser_background_check.setChecked(True)
        u.automation_auto_install_check.setChecked(True)
        u.windows_all_apps_check.setChecked(True)
        u.windows_auto_execute_check.setChecked(True)
        u.windows_compact_check.setChecked(False)
        u.windows_apps_paths.setPlainText(r'C:\Apps\demo.exe')
        self.assertTrue(u.settings_dirty());u.save_settings()
        saved=config.load_config()
        self.assertTrue(saved['windows_apps_enabled'])
        self.assertTrue(saved['browser_background'])
        self.assertTrue(saved['automation_auto_install'])
        self.assertTrue(saved['windows_apps_all_installed'])
        self.assertTrue(saved['windows_apps_auto_execute'])
        self.assertFalse(saved['windows_apps_compact'])
        self.assertEqual(saved['windows_apps_allowed'],[r'C:\Apps\demo.exe'])
        u.windows_apps_paths.setPlainText(r'C:\Apps\other.exe')
        self.assertTrue(u.settings_dirty());u.discard_settings()
        self.assertEqual(u.windows_apps_paths.toPlainText(),r'C:\Apps\demo.exe')
        self.assertFalse(u.settings_dirty())

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
        self.assertIn('h1 {font-size:21px;font-weight:600;}',css)

    def test_old_font_restored_once_and_future_choice_retained(self):
        first=config.load_config()
        self.assertEqual(first['font_size'],13)
        self.assertEqual(first['chat_font_revision'],2)
        first['font_size']=15;config.save_config(first)
        self.assertEqual(config.load_config()['font_size'],15)
