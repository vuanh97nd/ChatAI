import tempfile
import unittest
from pathlib import Path,PosixPath
from types import SimpleNamespace
from unittest.mock import patch
from assistant.automation_setup import ensure_dependencies,PACKAGES
from assistant.windows_apps import WindowsApps,resume_automation,stop_automation,validate_settings


class AutomationPermissionsTest(unittest.TestCase):
    def setUp(self):resume_automation()
    def tearDown(self):resume_automation()
    def test_default_permissions_off_and_strict_booleans(self):
        cfg={};validate_settings(cfg)
        self.assertFalse(cfg['automation_auto_install']);self.assertFalse(cfg['windows_apps_all_installed'])
        for flag in ('automation_auto_install','windows_apps_all_installed'):
            with self.assertRaises(ValueError):validate_settings({flag:'yes'})
    def test_registry_discovery_resolves_icons_and_filters_non_apps(self):
        from assistant.installed_apps import installed_apps
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder)/'demo.exe';app.write_bytes(b'fixture')
            setup=Path(folder)/'setup.exe';setup.write_bytes(b'fixture')
            class Key:
                def __init__(self,values=None,children=None):self.values=values or {};self.children=children or {}
                def __enter__(self):return self
                def __exit__(self,*args):pass
            apps=Key(children={'demo.exe':Key({None:str(app)}),'relative.exe':Key({None:'demo.exe'}),'setup.exe':Key({None:str(setup)})})
            uninstall=Key(children={'demo':Key({'DisplayName':'Demo App','DisplayIcon':'"'+str(app)+'",0'})})
            def open_key(parent,name,*args):
                return parent.children[name] if isinstance(parent,Key) else apps if name.endswith('App Paths') else uninstall
            registry=SimpleNamespace(HKEY_CURRENT_USER='user',HKEY_LOCAL_MACHINE='machine',
                KEY_WOW64_64KEY=64,KEY_WOW64_32KEY=32,KEY_READ=1,OpenKey=open_key,
                QueryInfoKey=lambda key:(len(key.children),0,0),EnumKey=lambda key,index:list(key.children)[index],
                QueryValueEx=lambda key,name:(key.values[name],1))
            with patch.dict('sys.modules',{'winreg':registry}),patch('os.name','nt'),patch('assistant.installed_apps.Path',PosixPath):
                rows=installed_apps()
            self.assertEqual(rows,[{'name':'Demo App','path':str(app)}])
    def test_all_apps_only_authorizes_discovered_executables_and_revocation(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder)/'demo.exe';app.write_bytes(b'fixture')
            unknown=Path(folder)/'unknown.exe';unknown.write_bytes(b'fixture')
            cfg={'windows_apps_enabled':True,'windows_apps_all_installed':True,'windows_apps_allowed':[]}
            tools=WindowsApps(cfg,lambda *a:None,backend=SimpleNamespace())
            with patch('assistant.installed_apps.installed_apps',return_value=[{'name':'Demo','path':str(app)}]):
                plan=tools.prepare('windows_open',{'path':str(app)})
                self.assertEqual(plan['path'],str(app))
                with self.assertRaises(PermissionError):tools.prepare('windows_open',{'path':str(unknown)})
                listing=tools.commit(tools.prepare('windows_list_apps',{'query':'demo'}))
                self.assertEqual(listing['apps'][0]['path'],str(app))
                cfg['windows_apps_all_installed']=False
                with self.assertRaises(PermissionError):tools.commit(plan)
    def test_installer_never_runs_without_permission(self):
        with patch('assistant.automation_setup.subprocess.Popen') as launch:
            ensure_dependencies({})
            ensure_dependencies({'automation_auto_install':True,'windows_apps_enabled':False})
            launch.assert_not_called()
    def test_installer_uses_exact_runtime_and_fixed_packages(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder);python=runtime/'python.exe';python.write_bytes(b'fixture')
            (runtime/'chat-ai-runtime.json').write_text('{}')
            process=SimpleNamespace(poll=lambda:0,returncode=0)
            cfg={'automation_auto_install':True,'windows_apps_enabled':True,'package':'malicious'}
            with patch('os.name','nt'),patch('assistant.automation_setup.Path',PosixPath),patch('assistant.automation_setup.sys.executable',str(runtime/'pythonw.exe')),patch('assistant.automation_setup.sys.prefix','base'),patch('assistant.automation_setup.sys.base_prefix','base'),patch('assistant.automation_setup.missing_modules',side_effect=[['playwright','docx'],[]]),patch('assistant.automation_setup.subprocess.Popen',return_value=process) as launch:
                ensure_dependencies(cfg)
            command=launch.call_args.args[0]
            self.assertEqual(command[0],str(python));self.assertIn(PACKAGES['playwright'],command);self.assertIn('python-docx>=1.1,<2',command);self.assertNotIn('docx',command)
            self.assertNotIn('malicious',command);self.assertFalse(launch.call_args.kwargs['shell'])
            self.assertEqual(launch.call_args.kwargs['creationflags'],0x08000000)
            self.assertEqual(launch.call_args.kwargs['stdin'],__import__('subprocess').DEVNULL)
    def test_global_python_is_not_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            python=Path(folder)/'python.exe';python.write_bytes(b'fixture')
            cfg={'automation_auto_install':True,'windows_apps_enabled':True}
            with patch('os.name','nt'),patch('assistant.automation_setup.Path',PosixPath),patch('assistant.automation_setup.sys.executable',str(python)),patch('assistant.automation_setup.sys.prefix','base'),patch('assistant.automation_setup.sys.base_prefix','base'),patch('assistant.automation_setup.missing_modules',return_value=['playwright']),patch('assistant.automation_setup.subprocess.Popen') as launch:
                with self.assertRaises(RuntimeError):ensure_dependencies(cfg)
                launch.assert_not_called()
    def test_stop_prevents_install(self):
        stop_automation()
        with tempfile.TemporaryDirectory() as folder:
            python=Path(folder)/'python.exe';python.write_bytes(b'fixture')
            (python.parent/'chat-ai-runtime.json').write_text('{}')
            with patch('os.name','nt'),patch('assistant.automation_setup.Path',PosixPath),patch('assistant.automation_setup.sys.executable',str(python)),patch('assistant.automation_setup.missing_modules',return_value=['playwright']),patch('assistant.automation_setup.subprocess.Popen') as launch:
                with self.assertRaises(PermissionError):ensure_dependencies({'automation_auto_install':True,'windows_apps_enabled':True})
                launch.assert_not_called()
    def test_revocation_stops_running_install(self):
        with tempfile.TemporaryDirectory() as folder:
            python=Path(folder)/'python.exe';python.write_bytes(b'fixture')
            (python.parent/'chat-ai-runtime.json').write_text('{}')
            cfg={'automation_auto_install':True,'windows_apps_enabled':True}
            class Process:
                done=False
                def poll(self):cfg['automation_auto_install']=False;return 0 if self.done else None
                def terminate(self):self.done=True
                def wait(self,timeout=None):return 0
            process=Process()
            with patch('os.name','nt'),patch('assistant.automation_setup.Path',PosixPath),patch('assistant.automation_setup.sys.executable',str(python)),patch('assistant.automation_setup.missing_modules',return_value=['playwright']),patch('assistant.automation_setup.subprocess.Popen',return_value=process):
                with self.assertRaises(PermissionError):ensure_dependencies(cfg)
                self.assertTrue(process.done)
