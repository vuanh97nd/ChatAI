import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.model_preferences import load_model,save_model,CLOUD_MODEL

class ModelPreferencesTest(unittest.TestCase):
    def test_private_persistent_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'history.db';store=Store(path)
            a={'username':'Alice','endpoint':'https://a.example/'}
            b={'username':'Bob','endpoint':'https://a.example'}
            self.assertEqual(load_model(store,None),CLOUD_MODEL)
            self.assertEqual(load_model(store,a),'qwen2.5:3b')
            save_model(store,a,'qwen2.5:7b')
            self.assertEqual(load_model(Store(path),a),'qwen2.5:7b')
            self.assertEqual(load_model(store,b),'qwen2.5:3b')
            self.assertEqual(load_model(store,dict(a,endpoint='https://b.example')),'qwen2.5:3b')
            with self.assertRaises(ValueError):save_model(store,a,'invalid')
            self.assertEqual(load_model(store,a),'qwen2.5:7b')
            save_model(store,a,CLOUD_MODEL)
            self.assertEqual(load_model(store,a),CLOUD_MODEL)
