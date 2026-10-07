import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from assistant.modules import ModuleManager,DownloadStopped
from assistant.storage import Store


class DownloadControlsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'data').mkdir()
        self.store=Store(self.root/'history.db')
        self.manager=ModuleManager(self.store,Mock(),self.root)
    def tearDown(self):self.temp.cleanup()

    def test_stop_applies_to_model_only(self):
        m=self.manager;m.busy=True;m.active_target='office'
        with self.assertRaises(RuntimeError):m.stop_download('cancelled')
        m.active_target='qwen2.5:3b';m.stop_download('paused')
        self.assertEqual(m.stop_action,'paused')
        with self.assertRaises(DownloadStopped):m.check_stopped()

    def test_pause_closes_pull_stream(self):
        m=self.manager;m.busy=True;m.active_target='qwen2.5:3b';closed=[]
        def stream():
            try:
                m.stop_download('paused')
                yield SimpleNamespace(status='downloading',total=100,completed=1,digest='a')
            finally:closed.append(True)
        m.client.pull=Mock(return_value=stream())
        with self.assertRaises(DownloadStopped):m.pull('job','qwen2.5:3b')
        self.assertEqual(closed,[True])

    def test_resume_does_not_mark_old_job_until_request_succeeds(self):
        m=self.manager
        with self.store.connection() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',('old','qwen2.5:3b','paused',None,'paused','now'))
        m.request=Mock(side_effect=RuntimeError('busy'))
        with self.assertRaises(RuntimeError):m.resume_download()
        self.assertEqual(m.jobs()[0]['status'],'paused')
        m.request=Mock(return_value='new')
        self.assertEqual(m.resume_download(),'new')
        self.assertEqual(m.jobs()[0]['status'],'resumed')

    def test_remove_confirms_absence_and_preserves_conversations(self):
        m=self.manager;cid=self.store.create()
        with self.store.connection() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',('delete','qwen2.5:3b','queued',None,'queued','now'))
        m.installed_models=Mock(side_effect=[{'qwen2.5:3b'},set()])
        m.client.delete=Mock()
        m.remove_worker('delete','qwen2.5:3b')
        m.client.delete.assert_called_once_with('qwen2.5:3b')
        self.assertEqual(m.jobs()[0]['status'],'removed')
        self.assertEqual(self.store.load(cid)['messages'],[])
        self.assertFalse(m.busy)

    def test_remove_rejects_unknown_or_busy(self):
        m=self.manager
        with self.assertRaises(ValueError):m.remove_model('other-model')
        m.busy=True
        with self.assertRaises(RuntimeError):m.remove_model('qwen2.5:3b')

    def test_added_coding_models_and_capabilities(self):
        from assistant.modules import CHAT_MODELS,ALLOWED_MODELS
        from assistant.model_preferences import valid_model
        expected={'deepseek-coder-v2:16b':False,'qwen2.5-coder:32b':True,'codestral:22b':False,'deepseek-coder:33b':False}
        for name,tools in expected.items():
            with self.subTest(name=name):
                self.assertIn(name,ALLOWED_MODELS);self.assertTrue(valid_model(name))
                self.assertEqual(CHAT_MODELS[name]['tools'],tools)
                self.assertTrue(CHAT_MODELS[name]['large']);self.assertTrue(CHAT_MODELS[name]['warning'])
                self.assertGreater(CHAT_MODELS[name]['disk_gb'],CHAT_MODELS[name]['download_gb'])
