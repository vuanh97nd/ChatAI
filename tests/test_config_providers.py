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
