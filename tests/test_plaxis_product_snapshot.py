import unittest
from types import SimpleNamespace

from assistant.plaxis_commands import model_snapshot
from assistant.online_automation import model_warnings


class ProductSnapshotTests(unittest.TestCase):
    def test_zero_enum_is_only_labelled_plane_strain_for_2d(self):
        g=SimpleNamespace(Project=SimpleNamespace(ModelType=SimpleNamespace(value=0)))
        self.assertIn('ModelType=Plane strain',model_snapshot(g,version='2d'))
        for version in ('3d',None):
            text=model_snapshot(g,version=version)
            self.assertNotIn('ModelType=Plane strain',text)
            self.assertIn('ModelType raw=0',text)

    def test_3d_pile_does_not_trigger_axisymmetric_warning(self):
        self.assertEqual(model_warnings('Project: ModelType=Plane strain (0)',
            {'product':'3d','title':'Loading of a suction pile'}),[])

    def test_2d_circular_footing_still_warns(self):
        self.assertTrue(model_warnings('Project: ModelType=Plane strain (0)',
            {'product':'2d','title':'Settlement of a circular footing on sand'}))
