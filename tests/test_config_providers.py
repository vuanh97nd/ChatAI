import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from assistant import config
from assistant.cloud import REMOTE_MODELS


class ConfigProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = json.loads((config.ROOT / 'config.json').read_text(encoding='utf-8'))
        self.original.update(api_provider_revision=2, chat_font_revision=2, whitelist=['workspace'])
        (self.root / 'config.json').write_text(json.dumps(self.original), encoding='utf-8')
        self.patch = patch.object(config, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_groq_selection_survives_save_and_restart(self):
        saved = config.save_config(dict(self.original, chat_provider='groq'))
        self.assertEqual(saved['chat_provider'], 'groq')
        self.assertEqual(config.load_config()['chat_provider'], 'groq')
        self.assertTrue(list((self.root / 'data/backups').glob('config-*.json')))

    def test_fresh_install_defaults_to_online_nvidia(self):
        import build_runtime
        original = dict(self.original, chat_provider='deepseek_flash')
        source = json.dumps(original)
        (self.root / 'config.json').write_text(source, encoding='utf-8')
        with patch.object(build_runtime, 'ROOT', self.root):
            build_runtime.installer_config()
        bundled = json.loads((self.root / 'installer-assets/config.json').read_text(encoding='utf-8'))
        self.assertEqual(bundled['chat_provider'], 'nvidia')
        self.assertEqual((self.root / 'config.json').read_text(encoding='utf-8'), source)
        self.assertIn('nvidia', REMOTE_MODELS.values())

    def test_missing_provider_defaults_to_nvidia(self):
        cfg = dict(self.original)
        cfg.pop('chat_provider')
        cfg.pop('api_provider_revision')
        self.assertEqual(config.validate_config(cfg)['chat_provider'], 'nvidia')

    def test_startup_skips_unavailable_folder_without_granting_replacement(self):
        cfg = dict(self.original, whitelist=['missing-desktop'])
        (self.root/'config.json').write_text(json.dumps(cfg), encoding='utf-8')
        original_mkdir = Path.mkdir
        bad = self.root/'missing-desktop'
        def mkdir(path, *args, **kwargs):
            if path == bad: raise FileNotFoundError('Desktop target missing')
            return original_mkdir(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', mkdir):
            loaded = config.load_config()
            self.assertEqual(loaded['roots'], [])
            self.assertEqual(loaded['whitelist'], ['missing-desktop'])
            with self.assertRaises(FileNotFoundError): config.save_config(cfg)
        persisted=json.loads((self.root/'config.json').read_text(encoding='utf-8'))
        self.assertEqual(persisted['whitelist'], ['missing-desktop'])

    def test_startup_keeps_accessible_folders_and_still_rejects_project_root(self):
        cfg=dict(self.original, whitelist=['blocked','workspace'])
        original_mkdir=Path.mkdir
        def mkdir(path,*args,**kwargs):
            if path==self.root/'blocked':raise PermissionError('blocked')
            return original_mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',mkdir):
            loaded=config.validate_config(cfg,allow_unavailable_roots=True)
        self.assertEqual(loaded['roots'], [self.root/'workspace'])
        with self.assertRaises(ValueError):
            config.validate_config(dict(self.original,whitelist=['.']),allow_unavailable_roots=True)

    def test_account_settings_can_be_saved_with_old_inaccessible_desktop(self):
        cfg=dict(self.original,whitelist=['old-desktop','workspace'],custom_ai=[],procedure_training_enabled=True)
        original_mkdir=Path.mkdir
        def mkdir(path,*args,**kwargs):
            if path==self.root/'old-desktop':raise PermissionError('Access denied')
            return original_mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',mkdir):
            saved=config.save_config(cfg,allow_unavailable_roots=True)
            restored=config.load_config()
        self.assertEqual(saved['roots'],[self.root/'workspace'])
        self.assertEqual(restored['whitelist'],['old-desktop','workspace'])
        self.assertTrue(restored['procedure_training_enabled'])
        self.assertTrue(list((self.root/'data/backups').glob('config-*.json')))

    def test_ai_preferences_preserve_unavailable_grants_but_new_folder_stays_strict(self):
        current=dict(self.original,whitelist=['old-desktop','workspace'])
        original_mkdir=Path.mkdir
        def mkdir(path,*args,**kwargs):
            if path in {self.root/'old-desktop',self.root/'new-denied'}:raise PermissionError('Access denied')
            return original_mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',mkdir):
            saved=config.save_preferences(dict(current,nvidia_model='nvidia/new-model'),current)
            self.assertEqual(saved['nvidia_model'],'nvidia/new-model')
            self.assertEqual(saved['roots'],[self.root/'workspace'])
            persisted=(self.root/'config.json').read_bytes()
            with self.assertRaises(PermissionError):
                config.save_preferences(dict(current,whitelist=['workspace','new-denied']),current)
            self.assertEqual((self.root/'config.json').read_bytes(),persisted)
            with self.assertRaises(PermissionError):
                config.save_preferences(dict(current,task_user_folders_enabled=not current.get('task_user_folders_enabled',False)),current)

    def test_legacy_revision_preserves_existing_provider_choice(self):
        for provider in ('local', 'deepseek_flash', 'groq', 'nvidia'):
            with self.subTest(provider=provider):
                cfg = dict(self.original, chat_provider=provider)
                cfg.pop('api_provider_revision')
                config.save_config(cfg)
                self.assertEqual(config.load_config()['chat_provider'], provider)

    def test_all_builtin_online_choices_can_be_saved(self):
        for provider in set(REMOTE_MODELS.values()):
            if provider.startswith('ai_'):
                continue
            with self.subTest(provider=provider):
                config.save_config(dict(self.original, chat_provider=provider))
                self.assertEqual(config.load_config()['chat_provider'], provider)

    def test_unknown_provider_is_rejected_without_overwriting_settings(self):
        previous = (self.root / 'config.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Dịch vụ AI không hợp lệ'):
            config.save_config(dict(self.original, chat_provider='not-a-provider'))
        self.assertEqual((self.root / 'config.json').read_bytes(), previous)
