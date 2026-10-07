"""Benchmark failures must never be scored as model answers."""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluation import run_baseline


class BaselineTest(unittest.TestCase):
    def run_case(self, client):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'evaluation').mkdir()
            (root / 'evaluation/questions.json').write_text(json.dumps([
                {'id': 22, 'category': 'writing_translation',
                 'question': 'Dịch: The meeting has been postponed until Friday.',
                 'criteria': 'Hoãn đến thứ Sáu.'}]))
            cfg = {'ollama_host': 'http://127.0.0.1:11434', 'default_model': 'qwen2.5:7b',
                   'num_ctx': 4096, 'num_predict': 1000, 'max_rounds': 4, 'roots': [],
                   'temperature': .2}
            args = argparse.Namespace(model=None, ids=None, all=False, no_tools=True,
                                      web=False, verbose=False, label='test')
            with patch.object(run_baseline, 'ROOT_DIR', root), \
                 patch('assistant.config.load_config', return_value=cfg), \
                 patch('ollama.Client', return_value=client), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = run_baseline.run(args)
            saved = json.loads(next((root / 'data').glob('baseline-*.json')).read_text())
            self.assertEqual(result, saved)
            return result

    def test_connection_failure_is_not_scored(self):
        class Offline:
            def chat(self, **kwargs):
                raise ConnectionError('connection refused')
        result = self.run_case(Offline())
        row = result['rows'][0]
        self.assertEqual(row['status'], 'error')
        self.assertEqual(row['answer'], '')
        self.assertIsNone(row['auto_pass'])
        self.assertEqual(result['summary']['errors'], 1)
        self.assertEqual(result['summary']['auto_pass'], '0/0')
        self.assertIsNone(result['summary']['avg_seconds'])

    def test_real_answer_remains_eligible_for_scoring(self):
        from types import SimpleNamespace
        class Online:
            def chat(self, **kwargs):
                if kwargs.get('format'):
                    return {'message': {'content': json.dumps(dict(
                        category='writing_translation', creative=False,
                        complex=False, high_accuracy=False))}}
                return iter([SimpleNamespace(message=SimpleNamespace(
                    content='Cuộc họp đã được hoãn đến thứ Sáu.', tool_calls=[]))])
        row = self.run_case(Online())['rows'][0]
        self.assertEqual(row['status'], 'answered')
        self.assertIsNone(row['error'])
        self.assertTrue(row['auto_pass'])

    def test_cli_returns_failure_when_run_has_errors(self):
        with patch('sys.argv', ['run_baseline.py']), \
             patch.object(run_baseline, 'run', return_value={
                 'summary': {'errors': 1, 'empty_answers': 1}}):
            self.assertEqual(run_baseline.main(), 1)
