import unittest
from unittest.mock import Mock
from assistant.capabilities import Capabilities


class GeotechnicalDispatchTest(unittest.TestCase):
    def test_new_registered_write_tools_prepare_and_commit_their_components(self):
        capabilities=Capabilities.__new__(Capabilities)
        capabilities.active={'plaxis_app','geoslope_app'}
        capabilities.plaxis_app=Mock();capabilities.geoslope_app=Mock()
        for name,component in [('plaxis_generate_script',capabilities.plaxis_app),('geoslope_create',capabilities.geoslope_app)]:
            with self.subTest(tool=name):
                args={'project_name':'Fixture','problem':'{}'};plan={'action':name}
                component.prepare.return_value=plan;component.commit.return_value={'ok':True,'path':'fixture'}
                self.assertEqual(capabilities.prepare(name,args),plan)
                self.assertEqual(capabilities.commit(plan),{'ok':True,'path':'fixture'})
                component.prepare.assert_called_once_with(name,args);component.commit.assert_called_once_with(plan)
        capabilities.active.clear()
        with self.assertRaises(RuntimeError):capabilities.commit({'action':'geoslope_create'})
        self.assertEqual(capabilities.geoslope_app.commit.call_count,1)
