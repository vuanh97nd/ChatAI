import sys
import unittest
from assistant.runtime_compat import prepare_six


class RuntimeCompatTest(unittest.TestCase):
    def test_six_and_other_importers(self):
        try:import six
        except ImportError:self.skipTest('six absent')
        importer=type('_SixMetaPathImporter',(),{})()
        normal=type('OtherImporter',(),{})()
        sys.meta_path.extend([importer,normal])
        try:
            prepare_six();self.assertEqual(importer._path,[]);self.assertFalse(hasattr(normal,'_path'))
            importer._path=['existing'];prepare_six();self.assertEqual(importer._path,['existing'])
            import six.moves
            self.assertIsInstance(repr(six.moves),str)
        finally:
            sys.meta_path.remove(importer);sys.meta_path.remove(normal)
