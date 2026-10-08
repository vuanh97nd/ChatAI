"""Tests for PlaxisUIAutomationApp and plaxis_ui_automation module.

All Windows/pywinauto code paths are mocked. Tests verify:
  - available() returns False on non-Windows / missing deps
  - run_plaxis_automation() returns graceful error when unavailable
  - StepLog records steps correctly
  - run_plaxis_automation() succeeds with all steps mocked
  - prepare() validates inputs
  - commit() builds correct response structure
  - Tool registry contains plaxis_ui_automation
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


EXCAVATION_PROBLEM = json.dumps({
    'type': 'excavation_pit',
    'excavation_depth': 5.0,
    'excavation_width': 8.0,
    'wall_thickness': 0.5,
    'embedment_depth': 2.0,
    'surcharge': 10.0,
    'soil_layers': [
        {'name': 'Cat', 'E': 18000, 'nu': 0.30, 'gamma': 18.5,
         'c': 5, 'phi': 28, 'thickness': 5.0},
        {'name': 'Set', 'E': 7000,  'nu': 0.35, 'gamma': 17.0,
         'c': 20, 'phi': 16, 'thickness': 5.0},
    ],
})

SLOPE_PROBLEM = json.dumps({
    'type': 'slope_stability',
    'slope_angle': 30.0,
    'slope_height': 5.0,
    'analysis': 'Bishop',
    'soil_layers': [
        {'name': 'Dat set', 'E': 12000, 'nu': 0.3,
         'gamma': 19.0, 'c': 20, 'phi': 25, 'thickness': 8.0},
    ],
})


def _make_automation_app(tmp_dir=None):
    from assistant.plaxis_ui_automation import PlaxisUIAutomationApp
    tmp = tmp_dir or tempfile.mkdtemp()
    files = MagicMock()
    files.roots = [Path(tmp)]
    audit = MagicMock()
    return PlaxisUIAutomationApp(files, audit), tmp


# ── available() ──────────────────────────────────────────────────────────────

class TestAvailable(unittest.TestCase):
    def test_not_available_on_posix(self):
        from assistant.plaxis_ui_automation import available
        with patch.object(os, 'name', 'posix'):
            self.assertFalse(available())

    def test_not_available_when_deps_missing(self):
        from assistant.plaxis_ui_automation import available
        with patch.object(os, 'name', 'nt'), \
             patch.dict(sys.modules, {'pywinauto': None, 'psutil': None}):
            self.assertFalse(available())


# ── run_plaxis_automation() error paths ──────────────────────────────────────

class TestRunAutomationErrors(unittest.TestCase):
    def _problem(self):
        from assistant.plaxis_app import _validate_problem
        return _validate_problem(EXCAVATION_PROBLEM)

    def test_returns_error_when_not_available(self):
        from assistant.plaxis_ui_automation import run_plaxis_automation
        with patch('assistant.plaxis_ui_automation.available', return_value=False):
            r = run_plaxis_automation(self._problem())
        self.assertFalse(r['executed'])
        self.assertIn('Windows', r['error'])

    def test_returns_error_when_plaxis_not_found_no_exe(self):
        from assistant.plaxis_ui_automation import run_plaxis_automation
        with patch('assistant.plaxis_ui_automation.available', return_value=True), \
             patch('assistant.plaxis_ui_automation._find_or_launch',
                   side_effect=RuntimeError('Plaxis chưa chạy và không có plaxis_exe')):
            r = run_plaxis_automation(self._problem(), shot_dir=tempfile.mkdtemp())
        self.assertFalse(r['executed'])
        self.assertIn('plaxisexe', r['error'].lower().replace(' ', '').replace('_', ''))

    def test_partial_steps_returned_on_mid_failure(self):
        from assistant.plaxis_ui_automation import run_plaxis_automation, StepLog
        mock_proc = MagicMock(); mock_proc.pid = 111
        mock_win  = MagicMock()

        def fake_new_project(win, log):
            log.record(win, '01_new_project', note='ok')

        def fake_soil_mode(win, log):
            log.fail(win, '02_soil_mode', 'UIA error')

        tmp = tempfile.mkdtemp()
        with patch('assistant.plaxis_ui_automation.available', return_value=True), \
             patch('assistant.plaxis_ui_automation._find_or_launch', return_value=mock_proc), \
             patch('assistant.plaxis_ui_automation._main_window', return_value=mock_win), \
             patch('assistant.plaxis_ui_automation._shot', return_value='/tmp/x.png'), \
             patch('assistant.plaxis_ui_automation._step_new_project', fake_new_project), \
             patch('assistant.plaxis_ui_automation._step_soil_mode', fake_soil_mode):
            r = run_plaxis_automation(self._problem(), shot_dir=tmp)

        self.assertFalse(r['executed'])
        # Should have at least the 'open' screenshot + step 1 before failure
        self.assertGreaterEqual(len(r['steps']), 1)


# ── run_plaxis_automation() success path ─────────────────────────────────────

class TestRunAutomationSuccess(unittest.TestCase):
    def _problem(self):
        from assistant.plaxis_app import _validate_problem
        return _validate_problem(EXCAVATION_PROBLEM)

    def test_full_run_returns_executed_true(self):
        from assistant.plaxis_ui_automation import run_plaxis_automation
        mock_proc = MagicMock(); mock_proc.pid = 222
        mock_win  = MagicMock()
        tmp = tempfile.mkdtemp()

        def fake_shot(win, path):
            Path(path).write_bytes(b'PNG')
            return str(path)

        noop = lambda *a, **kw: None

        with patch('assistant.plaxis_ui_automation.available', return_value=True), \
             patch('assistant.plaxis_ui_automation._find_or_launch', return_value=mock_proc), \
             patch('assistant.plaxis_ui_automation._main_window', return_value=mock_win), \
             patch('assistant.plaxis_ui_automation._shot', side_effect=fake_shot), \
             patch('assistant.plaxis_ui_automation._step_new_project', noop), \
             patch('assistant.plaxis_ui_automation._step_soil_mode', noop), \
             patch('assistant.plaxis_ui_automation._step_add_borehole', noop), \
             patch('assistant.plaxis_ui_automation._step_add_soil_layers', noop), \
             patch('assistant.plaxis_ui_automation._step_structures_mode', noop), \
             patch('assistant.plaxis_ui_automation._step_draw_geometry_excavation', noop), \
             patch('assistant.plaxis_ui_automation._step_mesh_mode', noop), \
             patch('assistant.plaxis_ui_automation._step_staged_construction', noop), \
             patch('assistant.plaxis_ui_automation._step_calculate', noop), \
             patch('assistant.plaxis_ui_automation._step_view_results', noop):
            r = run_plaxis_automation(self._problem(), shot_dir=tmp)

        self.assertTrue(r['executed'])
        self.assertEqual(r['error'], '')

    def test_slope_problem_uses_generic_geometry_step(self):
        from assistant.plaxis_ui_automation import run_plaxis_automation
        from assistant.plaxis_app import _validate_problem
        problem = _validate_problem(SLOPE_PROBLEM)

        mock_proc = MagicMock(); mock_proc.pid = 333
        mock_win  = MagicMock()
        tmp = tempfile.mkdtemp()
        noop = lambda *a, **kw: None

        def fake_shot(win, path):
            Path(path).write_bytes(b'PNG')
            return str(path)

        generic_called = []

        def fake_generic(win, log, ptype):
            generic_called.append(ptype)

        with patch('assistant.plaxis_ui_automation.available', return_value=True), \
             patch('assistant.plaxis_ui_automation._find_or_launch', return_value=mock_proc), \
             patch('assistant.plaxis_ui_automation._main_window', return_value=mock_win), \
             patch('assistant.plaxis_ui_automation._shot', side_effect=fake_shot), \
             patch('assistant.plaxis_ui_automation._step_new_project', noop), \
             patch('assistant.plaxis_ui_automation._step_soil_mode', noop), \
             patch('assistant.plaxis_ui_automation._step_add_borehole', noop), \
             patch('assistant.plaxis_ui_automation._step_add_soil_layers', noop), \
             patch('assistant.plaxis_ui_automation._step_structures_mode', noop), \
             patch('assistant.plaxis_ui_automation._step_draw_geometry_generic', fake_generic), \
             patch('assistant.plaxis_ui_automation._step_mesh_mode', noop), \
             patch('assistant.plaxis_ui_automation._step_staged_construction', noop), \
             patch('assistant.plaxis_ui_automation._step_calculate', noop), \
             patch('assistant.plaxis_ui_automation._step_view_results', noop):
            r = run_plaxis_automation(problem, shot_dir=tmp)

        self.assertIn('slope_stability', generic_called)


# ── StepLog ───────────────────────────────────────────────────────────────────

class TestStepLog(unittest.TestCase):
    def test_record_appends_entry(self):
        from assistant.plaxis_ui_automation import StepLog
        tmp = tempfile.mkdtemp()
        log = StepLog(tmp)
        win = MagicMock()

        with patch('assistant.plaxis_ui_automation._shot', return_value='/tmp/s.png'):
            entry = log.record(win, 'test_step', note='hello')

        self.assertEqual(len(log.steps), 1)
        self.assertEqual(entry['step'], 'test_step')
        self.assertEqual(entry['status'], 'ok')
        self.assertEqual(entry['note'], 'hello')

    def test_fail_records_then_raises(self):
        from assistant.plaxis_ui_automation import StepLog
        tmp = tempfile.mkdtemp()
        log = StepLog(tmp)
        win = MagicMock()

        with patch('assistant.plaxis_ui_automation._shot', return_value='/tmp/s.png'):
            with self.assertRaises(RuntimeError):
                log.fail(win, 'bad_step', 'boom')

        self.assertEqual(len(log.steps), 1)
        self.assertEqual(log.steps[0]['status'], 'error')

    def test_screenshot_failure_does_not_crash(self):
        from assistant.plaxis_ui_automation import StepLog
        tmp = tempfile.mkdtemp()
        log = StepLog(tmp)
        win = MagicMock()

        with patch('assistant.plaxis_ui_automation._shot', side_effect=OSError('no PIL')):
            entry = log.record(win, 'fragile_step', note='ok')

        self.assertIsNone(entry['screenshot'])
        self.assertEqual(len(log.steps), 1)


# ── PlaxisUIAutomationApp.prepare() ──────────────────────────────────────────

class TestPrepare(unittest.TestCase):
    def setUp(self):
        self.app, self.tmp = _make_automation_app()

    def _prepare(self, **kwargs):
        defaults = {
            'project_name': 'AutoTest',
            'version': '2d',
            'problem': EXCAVATION_PROBLEM,
        }
        defaults.update(kwargs)
        return self.app.prepare('plaxis_ui_automation', defaults)

    def test_valid_returns_plan(self):
        plan = self._prepare()
        self.assertEqual(plan['action'], 'plaxis_ui_automation')
        self.assertIn('problem', plan)
        self.assertIn('shot_folder', plan)

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(version='5d')

    def test_empty_project_name_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(project_name='')

    def test_plaxis_exe_stored(self):
        exe = r'C:\Plaxis\PLAXIS2D.exe'
        plan = self._prepare(plaxis_exe=exe)
        self.assertEqual(plan['plaxis_exe'], exe)

    def test_problem_validated_before_plan(self):
        with self.assertRaises(ValueError):
            self._prepare(problem='not-json')


# ── PlaxisUIAutomationApp.commit() ────────────────────────────────────────────

class TestCommit(unittest.TestCase):
    def setUp(self):
        self.app, self.tmp = _make_automation_app()

    def _plan(self):
        return self.app.prepare('plaxis_ui_automation', {
            'project_name': 'CommitTest',
            'version': '2d',
            'problem': EXCAVATION_PROBLEM,
        })

    def test_commit_not_executed_returns_error(self):
        plan = self._plan()
        with patch('assistant.plaxis_ui_automation.run_plaxis_automation') as mock_run:
            mock_run.return_value = {
                'executed': False,
                'steps': [],
                'error': 'Không chạy được',
            }
            result = self.app.commit(plan)
        self.assertFalse(result['ok'])
        self.assertIn('Không chạy được', result['error'])

    def test_commit_success_returns_steps_and_screenshots(self):
        plan = self._plan()
        steps = [
            {'step': '01_new_project', 'status': 'ok', 'screenshot': '/s/01.png', 'note': 'ok'},
            {'step': '02_soil_mode',   'status': 'ok', 'screenshot': '/s/02.png', 'note': 'ok'},
            {'step': '11_done',        'status': 'ok', 'screenshot': '/s/11.png', 'note': 'done'},
        ]
        with patch('assistant.plaxis_ui_automation.run_plaxis_automation') as mock_run:
            mock_run.return_value = {'executed': True, 'steps': steps, 'error': ''}
            result = self.app.commit(plan)

        self.assertTrue(result['ok'])
        self.assertEqual(len(result['steps']), 3)
        self.assertEqual(result['screenshots'], ['/s/01.png', '/s/02.png', '/s/11.png'])
        self.assertIn('3', result['note'])  # "Tổng bước: 3"

    def test_commit_partial_success_ok_false(self):
        plan = self._plan()
        steps = [
            {'step': '00_open', 'status': 'ok', 'screenshot': '/s/0.png', 'note': 'open'},
            {'step': 'error',   'status': 'error', 'screenshot': None,    'note': 'boom'},
        ]
        with patch('assistant.plaxis_ui_automation.run_plaxis_automation') as mock_run:
            mock_run.return_value = {
                'executed': False, 'steps': steps, 'error': 'Bước thất bại',
            }
            result = self.app.commit(plan)

        self.assertFalse(result['ok'])
        self.assertEqual(len(result['steps']), 2)
        # Screenshots from ok steps still returned
        self.assertIn('/s/0.png', result['screenshots'])


# ── Tool registry ─────────────────────────────────────────────────────────────

class TestRegistry(unittest.TestCase):
    def test_plaxis_ui_automation_in_extra_tools(self):
        from assistant.tools import EXTRA_TOOLS, WRITES
        names = [t['function']['name'] for _, t in EXTRA_TOOLS]
        self.assertIn('plaxis_ui_automation', names)
        self.assertIn('plaxis_ui_automation', WRITES)

    def test_module_tag_correct(self):
        from assistant.tools import EXTRA_TOOLS
        mods = [m for m, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_ui_automation']
        self.assertEqual(mods, ['plaxis_ui_automation'])

    def test_schema_has_required_fields(self):
        from assistant.tools import EXTRA_TOOLS
        schema = next(t for _, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_ui_automation')
        fn = schema['function']
        for f in ('project_name', 'version', 'problem'):
            self.assertIn(f, fn['parameters']['required'])
        self.assertIn('plaxis_exe', fn['parameters']['properties'])


if __name__ == '__main__':
    unittest.main()
