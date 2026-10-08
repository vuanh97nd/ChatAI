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
