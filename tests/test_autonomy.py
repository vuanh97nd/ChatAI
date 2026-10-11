import unittest
from assistant.autonomy import GRANTS,grant_autonomy,task_tools_authorized

class AutonomyTests(unittest.TestCase):
    def test_explicit_grant_enables_supported_permissions_preserves_other_settings(self):
        old={'roots':['/workspace/user'],'custom_ai':[],'windows_apps_allowed':['C:/Apps/App.exe'],'other':'unchanged'}
        cfg=grant_autonomy(old)
        self.assertTrue(all(cfg[key] for key in GRANTS))
        self.assertEqual(cfg['roots'],old['roots']);self.assertEqual(cfg['other'],'unchanged')
        self.assertEqual(cfg['online_document_pages'],0)
        self.assertNotIn('ai_tools_auto_execute',old)
        self.assertTrue(task_tools_authorized(cfg))
    def test_profile_not_implicitly_enabled(self):
        self.assertFalse(task_tools_authorized({}))
        self.assertFalse(task_tools_authorized({'ai_tools_auto_execute':False}))

    def test_grant_preserves_selected_document_provider(self):
        self.assertEqual(grant_autonomy({'online_document_provider':'gemini'})['online_document_provider'],'gemini')

    def test_windows_folders_ignore_missing_paths_and_respect_redirection(self):
        import tempfile
        import os
        from pathlib import Path,PosixPath
        from types import SimpleNamespace
        from unittest.mock import patch
        from assistant.autonomy import windows_work_folders
        with tempfile.TemporaryDirectory() as folder:
            redirected=Path(folder)/'OneDriveDesktop';redirected.mkdir()
            extra=Path(folder)/'AI';extra.mkdir()
            class Key:
                def __enter__(self):return self
                def __exit__(self,*args):pass
            registry=SimpleNamespace(HKEY_CURRENT_USER=1,OpenKey=lambda *args:Key(),
                                     QueryValueEx=lambda *args:(str(redirected),1))
            extras=[str(extra),str(extra),str(extra/'missing')]
            expected=[str(redirected),str(extra)]
            home=PosixPath(folder)
            with patch.dict('sys.modules',{'os':SimpleNamespace(name='nt',path=os.path),'winreg':registry}),patch.object(PosixPath,'home',return_value=home):
                self.assertEqual(windows_work_folders(extras),expected)
