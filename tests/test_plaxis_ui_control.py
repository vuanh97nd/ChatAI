"""Tests for PlaxisUIControlApp and plaxis_ui_control module.

All tests run without a real Plaxis instance; Windows-only code paths
are exercised via mocks. Tests verify:
  - UI fallback is triggered when Remote Scripting port is closed
  - run_via_ui() returns correct error when pywinauto unavailable
  - run_via_ui() returns correct error when Plaxis not running (no exe given)
  - PlaxisUIControlApp.prepare() validates inputs
  - PlaxisUIControlApp.commit() delegates to run_via_ui correctly
  - plaxis_run_problem() auto-fallback path
  - Tool registry contains plaxis_ui_run
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


EXCAVATION_PROBLEM = json.dumps({
    'type': 'excavation_pit',
    'excavation_depth': 5.0,
    'excavation_width': 8.0,
    'wall_thickness': 0.5,
    'embedment_depth': 2.0,
    'surcharge': 10.0,
    'soil_layers': [
        {'name': 'Cat', 'E': 18000, 'nu': 0.30, 'gamma': 18.5, 'c': 5, 'phi': 28, 'thickness': 10.0},
    ],
})


def _make_plaxis_app(tmp_dir=None):
    from assistant.plaxis_app import PlaxisApp
    tmp = tmp_dir or tempfile.mkdtemp()
    files = MagicMock()
    files.roots = [Path(tmp)]
    files.path = lambda p, exists=True: Path(p)
    return PlaxisApp(files, MagicMock())


def _make_ui_app(tmp_dir=None):
    from assistant.plaxis_ui_control import PlaxisUIControlApp
    tmp = tmp_dir or tempfile.mkdtemp()
    plaxis_app = _make_plaxis_app(tmp)
    files = MagicMock()
    files.roots = [Path(tmp)]
    audit = MagicMock()
    return PlaxisUIControlApp(plaxis_app, files, audit), tmp


# ── available() ──────────────────────────────────────────────────────────────

class TestAvailable(unittest.TestCase):
    def test_not_available_on_non_windows(self):
        from assistant.plaxis_ui_control import available
        with patch.object(os, 'name', 'posix'):
            self.assertFalse(available())

    def test_not_available_when_pywinauto_missing(self):
        from assistant.plaxis_ui_control import available
        with patch.object(os, 'name', 'nt'):
            with patch.dict(sys.modules, {'pywinauto': None, 'psutil': None}):
                self.assertFalse(available())


# ── run_via_ui error paths ────────────────────────────────────────────────────

class TestRunViaUiErrors(unittest.TestCase):
    def test_returns_error_on_non_windows(self):
        from assistant.plaxis_ui_control import run_via_ui
        with patch('assistant.plaxis_ui_control.available', return_value=False):
            result = run_via_ui('# script', tempfile.mkdtemp(), '/tmp/shot.png')
        self.assertFalse(result['executed'])
        self.assertIn('Windows', result['error'])

    def test_returns_error_when_plaxis_not_running_no_exe(self):
        from assistant.plaxis_ui_control import run_via_ui
        with patch('assistant.plaxis_ui_control.available', return_value=True), \
             patch('assistant.plaxis_ui_control._find_plaxis_process', return_value=None):
            result = run_via_ui('# script', tempfile.mkdtemp(), '/tmp/shot.png', plaxis_exe=None)
        self.assertFalse(result['executed'])
        self.assertIn('plaxis_exe', result['error'].lower().replace(' ', ''))

    def test_returns_error_when_window_not_found(self):
        from assistant.plaxis_ui_control import run_via_ui
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with patch('assistant.plaxis_ui_control.available', return_value=True), \
             patch('assistant.plaxis_ui_control._find_plaxis_process', return_value=mock_proc), \
             patch('assistant.plaxis_ui_control._get_main_window',
                   side_effect=RuntimeError('No window')):
            result = run_via_ui('# script', tempfile.mkdtemp(), '/tmp/shot.png')
        self.assertFalse(result['executed'])
        self.assertIn('No window', result['error'])

    def test_successful_run_returns_screenshot_path(self):
        from assistant.plaxis_ui_control import run_via_ui
        tmp = tempfile.mkdtemp()
        shot_path = os.path.join(tmp, 'result.png')
        # Create a fake PNG so the mock "screenshot" exists
        Path(shot_path).write_bytes(b'FAKE_PNG')

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_window = MagicMock()

        with patch('assistant.plaxis_ui_control.available', return_value=True), \
             patch('assistant.plaxis_ui_control._find_plaxis_process', return_value=mock_proc), \
             patch('assistant.plaxis_ui_control._get_main_window', return_value=mock_window), \
             patch('assistant.plaxis_ui_control._run_script_via_menu'), \
             patch('assistant.plaxis_ui_control._wait_for_calculation'), \
             patch('assistant.plaxis_ui_control._take_screenshot', return_value=shot_path):
            result = run_via_ui('# script', tmp, shot_path)

        self.assertTrue(result['executed'])
        self.assertEqual(result['screenshot'], shot_path)
        self.assertEqual(result['mode'], 'ui_control')


# ── PlaxisUIControlApp.prepare() ─────────────────────────────────────────────

class TestUIControlPrepare(unittest.TestCase):
    def setUp(self):
        self.app, self.tmp = _make_ui_app()

    def _prepare(self, **kwargs):
        defaults = {'project_name': 'Test', 'version': '2d', 'problem': EXCAVATION_PROBLEM}
        defaults.update(kwargs)
        return self.app.prepare('plaxis_ui_run', defaults)

    def test_valid_args_returns_plan(self):
        plan = self._prepare()
        self.assertEqual(plan['action'], 'plaxis_ui_run')
        self.assertEqual(plan['version'], '2d')
        self.assertIn('script', plan)
        self.assertIn('screenshot_name', plan)

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(version='4d')

    def test_empty_project_name_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(project_name='')

    def test_plaxis_exe_stored_in_plan(self):
        exe = r'C:\Plaxis\PLAXIS2D.exe'
        plan = self._prepare(plaxis_exe=exe)
        self.assertEqual(plan['plaxis_exe'], exe)

    def test_no_exe_stored_as_none(self):
        plan = self._prepare()
        self.assertIsNone(plan['plaxis_exe'])


class TestUIControlCommit(unittest.TestCase):
    def setUp(self):
        self.app, self.tmp = _make_ui_app()

    def _make_plan(self):
        return self.app.prepare('plaxis_ui_run', {
            'project_name': 'CommitTest',
            'version': '2d',
            'problem': EXCAVATION_PROBLEM,
        })

    def test_commit_returns_error_when_not_executed(self):
        plan = self._make_plan()
        with patch('assistant.plaxis_ui_control.run_via_ui') as mock_run:
            mock_run.return_value = {
                'executed': False,
                'error': 'Plaxis chưa chạy',
                'screenshot': None,
                'mode': 'ui_control',
            }
            result = self.app.commit(plan)
        self.assertFalse(result['ok'])
        self.assertIn('Plaxis chưa chạy', result['error'])

    def test_commit_returns_ok_with_screenshot(self):
        plan = self._make_plan()
        shot = os.path.join(self.tmp, 'result.png')
        with patch('assistant.plaxis_ui_control.run_via_ui') as mock_run:
            mock_run.return_value = {
                'executed': True,
                'error': '',
                'screenshot': shot,
                'mode': 'ui_control',
                'note': f'Script đã chạy qua UI Control. Kết quả: ảnh chụp màn hình tại {shot}',
            }
            result = self.app.commit(plan)
        self.assertTrue(result['ok'])
        self.assertEqual(result['screenshot'], shot)
        self.assertIn(shot, result['files'])


# ── plaxis_run_problem fallback path ─────────────────────────────────────────

class TestRunPlaxisProblemFallback(unittest.TestCase):
    def test_auto_fallback_to_ui_when_remote_unavailable(self):
        from assistant.plaxis_remote import run_plaxis_problem

        with patch('assistant.plaxis_remote._connect',
                   side_effect=RuntimeError('port closed')), \
             patch('assistant.plaxis_remote._ui_control_fallback') as mock_ui:
            mock_ui.return_value = {
                'executed': True, 'mode': 'ui_control',
                'output': '', 'results': {}, 'screenshot': '/tmp/shot.png', 'error': '',
            }
            result = run_plaxis_problem(
                '# script', version='2d', ui_fallback=True,
                ui_script_dir='/tmp', ui_screenshot_path='/tmp/shot.png',
            )

        self.assertTrue(result['executed'])
        self.assertEqual(result['mode'], 'ui_control')
        mock_ui.assert_called_once()

    def test_no_fallback_returns_error_when_flag_false(self):
        from assistant.plaxis_remote import run_plaxis_problem

        with patch('assistant.plaxis_remote._connect',
                   side_effect=RuntimeError('port closed')):
            result = run_plaxis_problem('# script', version='2d', ui_fallback=False)

        self.assertFalse(result['executed'])
        self.assertEqual(result['mode'], 'remote_scripting')

    def test_remote_scripting_available_probe(self):
        from assistant.plaxis_remote import _remote_scripting_available
        import socket
        with patch.object(socket, 'create_connection', side_effect=OSError):
            self.assertFalse(_remote_scripting_available('2d'))

    def test_remote_scripting_available_when_port_open(self):
        from assistant.plaxis_remote import _remote_scripting_available
        import socket
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock())
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch.object(socket, 'create_connection', return_value=mock_cm):
            self.assertTrue(_remote_scripting_available('2d'))


# ── PlaxisRemoteApp commit uses fallback ──────────────────────────────────────

class TestRemoteAppWithFallback(unittest.TestCase):
    def _make_remote_app(self):
        from assistant.plaxis_remote import PlaxisRemoteApp
        app = PlaxisRemoteApp(_make_plaxis_app())
        return app

    def test_commit_shows_ui_mode_in_note(self):
        app = self._make_remote_app()
        plan = app.prepare('plaxis_run_problem', {
            'project_name': 'FallbackTest',
            'version': '2d',
            'problem': EXCAVATION_PROBLEM,
        })
        with patch('assistant.plaxis_remote.run_plaxis_problem') as mock_run:
            mock_run.return_value = {
                'executed': True, 'mode': 'ui_control',
                'output': '', 'results': {}, 'screenshot': '/tmp/r.png', 'error': '',
            }
            result = app.commit(plan)

        self.assertTrue(result['ok'])
        self.assertIn('ui control', result['note'].lower())
        self.assertEqual(result['mode'], 'ui_control')
        self.assertIn('screenshot', result)

    def test_commit_shows_remote_mode_in_note(self):
        app = self._make_remote_app()
        plan = app.prepare('plaxis_run_problem', {
            'project_name': 'RemoteTest',
            'version': '2d',
            'problem': EXCAVATION_PROBLEM,
        })
        with patch('assistant.plaxis_remote.run_plaxis_problem') as mock_run:
            mock_run.return_value = {
                'executed': True, 'mode': 'remote_scripting',
                'output': 'Hoan thanh', 'screenshot': None, 'error': '',
                'results': {
                    'max_settlement_mm': 30.0,
                    'max_horizontal_displacement_mm': 15.0,
                    'safety_factor': 1.5,
                    'phase_results': [],
                    'raw_summary': '',
                },
            }
            result = app.commit(plan)

        self.assertTrue(result['ok'])
        self.assertIn('remote scripting', result['note'].lower())
        self.assertAlmostEqual(result['max_settlement_mm'], 30.0, places=1)


# ── Tool registry ─────────────────────────────────────────────────────────────

class TestUIToolRegistry(unittest.TestCase):
    def test_plaxis_ui_run_in_extra_tools(self):
        from assistant.tools import EXTRA_TOOLS, WRITES
        names = [t['function']['name'] for _, t in EXTRA_TOOLS]
        self.assertIn('plaxis_ui_run', names)
        self.assertIn('plaxis_ui_run', WRITES)

    def test_plaxis_ui_run_module_tag(self):
        from assistant.tools import EXTRA_TOOLS
        modules = [m for m, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_ui_run']
        self.assertEqual(modules, ['plaxis_ui_control'])

    def test_plaxis_run_problem_has_plaxis_exe_param(self):
        from assistant.tools import EXTRA_TOOLS
        schema = next(t for _, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_run_problem')
        self.assertIn('plaxis_exe', schema['function']['parameters']['properties'])

    def test_plaxis_ui_run_has_required_fields(self):
        from assistant.tools import EXTRA_TOOLS
        schema = next(t for _, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_ui_run')
        fn = schema['function']
        for field in ('project_name', 'version', 'problem'):
            self.assertIn(field, fn['parameters']['required'])


if __name__ == '__main__':
    unittest.main()
