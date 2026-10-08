"""Tests for PlaxisRemoteApp and plaxis_remote module.

Unit tests (no real Plaxis needed) — uses mocks to verify:
  - Input validation
  - Script generation round-trip
  - Result extraction from mock Output server
  - Error paths (Plaxis not running, plxscripting not installed)

Integration notes (requires real Plaxis):
  Run with PLAXIS_INTEGRATION=1 to execute tests against a live Plaxis instance.
"""
import json
import sys
import unittest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

EXCAVATION_PROBLEM = json.dumps({
    'type': 'excavation_pit',
    'excavation_depth': 6.0,
    'excavation_width': 8.0,
    'wall_thickness': 0.5,
    'embedment_depth': 2.0,
    'surcharge': 20.0,
    'water_table_depth': 1.5,
    'soil_layers': [
        {'name': 'Cat pha', 'E': 20000, 'nu': 0.30, 'gamma': 18.5, 'c': 5,  'phi': 28, 'thickness': 4.0},
        {'name': 'Set',     'E': 8000,  'nu': 0.35, 'gamma': 17.0, 'c': 25, 'phi': 18, 'thickness': 6.0},
        {'name': 'Cat min', 'E': 15000, 'nu': 0.28, 'gamma': 18.0, 'c': 2,  'phi': 25, 'thickness': 8.0},
    ],
})

SLOPE_PROBLEM = json.dumps({
    'type': 'slope_stability',
    'slope_angle': 30.0,
    'slope_height': 5.0,
    'analysis': 'Bishop',
    'soil_layers': [
        {'name': 'Dat set', 'E': 12000, 'nu': 0.3, 'gamma': 19.0, 'c': 20, 'phi': 25, 'thickness': 8.0},
    ],
})

FOUNDATION_PROBLEM = json.dumps({
    'type': 'foundation_settlement',
    'footing_width': 2.0,
    'footing_depth': 1.5,
    'load': 400.0,
    'soil_layers': [
        {'name': 'Cat',  'E': 15000, 'nu': 0.3, 'gamma': 18.5, 'c': 5,  'phi': 28, 'thickness': 5.0},
        {'name': 'Set',  'E': 8000,  'nu': 0.35,'gamma': 17.0, 'c': 15, 'phi': 20, 'thickness': 5.0},
    ],
})

RETAINING_PROBLEM = json.dumps({
    'type': 'retaining_wall',
    'wall_height': 4.0,
    'wall_thickness': 0.35,
    'surcharge': 10.0,
    'soil_layers': [
        {'name': 'Cat', 'E': 20000, 'nu': 0.28, 'gamma': 18.0, 'c': 0, 'phi': 32, 'thickness': 6.0},
    ],
})


def _make_plaxis_app():
    """Create a PlaxisApp with a mock FileTools so no real disk access is needed."""
    import tempfile
    from pathlib import Path
    from assistant.plaxis_app import PlaxisApp

    tmp = tempfile.mkdtemp()
    files = MagicMock()
    files.roots = [Path(tmp)]
    files.path = lambda p, exists=True: Path(p)
    audit = MagicMock()
    return PlaxisApp(files, audit)


def _make_remote_app():
    from assistant.plaxis_remote import PlaxisRemoteApp
    return PlaxisRemoteApp(_make_plaxis_app())


# ── Validation tests ──────────────────────────────────────────────────────────

class TestPrepareValidation(unittest.TestCase):
    def setUp(self):
        self.app = _make_remote_app()

    def _prepare(self, **kwargs):
        defaults = {'project_name': 'Test', 'version': '2d', 'problem': EXCAVATION_PROBLEM}
        defaults.update(kwargs)
        return self.app.prepare('plaxis_run_problem', defaults)

    def test_valid_excavation_returns_plan(self):
        plan = self._prepare()
        self.assertEqual(plan['action'], 'plaxis_run_problem')
        self.assertEqual(plan['version'], '2d')
        self.assertEqual(plan['problem_type'], 'excavation_pit')
        self.assertIn('script', plan)

    def test_valid_slope(self):
        plan = self._prepare(problem=SLOPE_PROBLEM)
        self.assertEqual(plan['problem_type'], 'slope_stability')

    def test_valid_foundation(self):
        plan = self._prepare(problem=FOUNDATION_PROBLEM)
        self.assertEqual(plan['problem_type'], 'foundation_settlement')

    def test_valid_retaining(self):
        plan = self._prepare(problem=RETAINING_PROBLEM)
        self.assertEqual(plan['problem_type'], 'retaining_wall')

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(version='1d')

    def test_missing_project_name_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(project_name='')

    def test_bad_json_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(problem='not-json')

    def test_missing_type_raises(self):
        with self.assertRaises(ValueError):
            self._prepare(problem=json.dumps({'slope_angle': 30}))

    def test_3d_version_accepted(self):
        plan = self._prepare(version='3d')
        self.assertEqual(plan['version'], '3d')


class TestScriptGeneration(unittest.TestCase):
    """Verify that prepare() produces a syntactically correct script."""

    def _get_script(self, problem_json, version='2d'):
        app = _make_remote_app()
        plan = app.prepare('plaxis_run_problem', {
            'project_name': 'ScriptTest',
            'version': version,
            'problem': problem_json,
        })
        return plan['script']

    def test_excavation_script_has_new_server(self):
        script = self._get_script(EXCAVATION_PROBLEM)
        self.assertIn('new_server', script)

    def test_excavation_script_has_wall(self):
        script = self._get_script(EXCAVATION_PROBLEM)
        self.assertIn('g.plate(', script)

    def test_excavation_script_has_phases(self):
        script = self._get_script(EXCAVATION_PROBLEM)
        self.assertIn('g.phase(', script)

    def test_slope_script_has_bishop_label(self):
        script = self._get_script(SLOPE_PROBLEM)
        self.assertIn('Bishop', script)

    def test_foundation_script_has_lineload(self):
        script = self._get_script(FOUNDATION_PROBLEM)
        self.assertIn('lineload', script)

    def test_retaining_script_has_platemat(self):
        script = self._get_script(RETAINING_PROBLEM)
        self.assertIn('platemat', script)

    def test_water_table_in_excavation_script(self):
        script = self._get_script(EXCAVATION_PROBLEM)
        self.assertIn('setwaterlevel', script)

    def test_script_is_valid_python_syntax(self):
        import ast
        for prob in [EXCAVATION_PROBLEM, SLOPE_PROBLEM, FOUNDATION_PROBLEM, RETAINING_PROBLEM]:
            script = self._get_script(prob)
            # Strip the new_server import lines for syntax check
            lines = [l for l in script.splitlines()
                     if not l.startswith('from plxscripting') and not l.startswith('s, g =')]
            try:
                ast.parse('\n'.join(lines))
            except SyntaxError as e:
                self.fail(f'Script syntax error for {prob[:40]}: {e}')


# ── Result extraction tests ───────────────────────────────────────────────────

class TestExtractResults(unittest.TestCase):
    def _make_phase(self, uy_vals, ux_vals=None, stress_vals=None, sf=None, name='Phase1'):
        phase = MagicMock()
        phase.Identification = name
        if sf is not None:
            phase.Reached.SumMsf = sf
        else:
            del phase.Reached  # will raise AttributeError
        return phase, uy_vals, ux_vals or [], stress_vals or []

    def _make_g_out(self, phases_data):
        """Build a mock Plaxis Output globals object."""
        g_out = MagicMock()

        def getresults(phase, result_type, mode):
            idx = _find_phase_index(phases_data, phase)
            if 'Uy' in str(result_type):
                return phases_data[idx][1]
            if 'Ux' in str(result_type):
                return phases_data[idx][2]
            if 'EffectiveMeanStress' in str(result_type):
                return phases_data[idx][3]
            return []

        g_out.getresults.side_effect = getresults
        # Setup ResultTypes attribute paths
        g_out.ResultTypes.Soil.Deformations.Uy = 'Uy'
        g_out.ResultTypes.Soil.Deformations.Ux = 'Ux'
        g_out.ResultTypes.Soil.Stresses.EffectiveMeanStress = 'EffectiveMeanStress'
        return g_out

    def test_max_settlement_computed(self):
        from assistant.plaxis_remote import _extract_results

        phase = MagicMock()
        phase.Identification = 'Dao dat'
        del phase.Reached

        uy = [0.0, -0.015, -0.030, -0.010]  # max settlement = 30 mm
        ux = [0.0, 0.005, -0.005, 0.002]

        g_out = MagicMock()
        g_out.ResultTypes.Soil.Deformations.Uy = 'Uy'
        g_out.ResultTypes.Soil.Deformations.Ux = 'Ux'
        g_out.ResultTypes.Soil.Stresses.EffectiveMeanStress = 'Stress'

        call_count = [0]

        def getresults(ph, rt, mode):
            rt_s = str(rt)
            if 'Uy' in rt_s:
                return uy
            if 'Ux' in rt_s:
                return ux
            if 'Stress' in rt_s:
                return [50.0, 80.0, 120.0]
            return []

        g_out.getresults.side_effect = getresults

        results = _extract_results(g_out, [phase], 'excavation_pit')
        self.assertAlmostEqual(results['max_settlement_mm'], 30.0, places=1)
        self.assertAlmostEqual(results['max_horizontal_displacement_mm'], 5.0, places=1)
        self.assertAlmostEqual(results['max_stress_kpa'], 120.0, places=0)

    def test_safety_factor_extracted(self):
        from assistant.plaxis_remote import _extract_results

        phase = MagicMock()
        phase.Identification = 'SF Phase'
        phase.Reached.SumMsf = 1.456

        g_out = MagicMock()
        g_out.ResultTypes.Soil.Deformations.Uy = 'Uy'
        g_out.ResultTypes.Soil.Deformations.Ux = 'Ux'
        g_out.ResultTypes.Soil.Stresses.EffectiveMeanStress = 'Stress'
        g_out.getresults.return_value = []

        results = _extract_results(g_out, [phase], 'excavation_pit')
        self.assertAlmostEqual(results['safety_factor'], 1.456, places=3)

    def test_no_phases_returns_empty(self):
        from assistant.plaxis_remote import _extract_results

        g_out = MagicMock()
        results = _extract_results(g_out, [], 'slope_stability')
        self.assertIsNone(results['max_settlement_mm'])
        self.assertIsNone(results['safety_factor'])

    def test_phase_results_list_populated(self):
        from assistant.plaxis_remote import _extract_results

        phases = []
        for i, sf in enumerate([None, None, 1.35]):
            p = MagicMock()
            p.Identification = f'Phase{i}'
            if sf is not None:
                p.Reached.SumMsf = sf
            else:
                del p.Reached
            phases.append(p)

        g_out = MagicMock()
        g_out.ResultTypes.Soil.Deformations.Uy = 'Uy'
        g_out.ResultTypes.Soil.Deformations.Ux = 'Ux'
        g_out.ResultTypes.Soil.Stresses.EffectiveMeanStress = 'Stress'

        def getresults(ph, rt, mode):
            if 'Uy' in str(rt):
                return [-0.01, -0.02]
            return []

        g_out.getresults.side_effect = getresults

        results = _extract_results(g_out, phases, 'excavation_pit')
        self.assertEqual(len(results['phase_results']), 3)
        self.assertAlmostEqual(results['safety_factor'], 1.35, places=2)


# ── Error path tests ──────────────────────────────────────────────────────────

class TestRunPlaxisProblemErrors(unittest.TestCase):
    def test_import_error_returns_not_executed(self):
        from assistant.plaxis_remote import run_plaxis_problem

        with patch.dict(sys.modules, {'plxscripting': None, 'plxscripting.easy': None}):
            result = run_plaxis_problem('# dummy script', version='2d')

        self.assertFalse(result['executed'])
        self.assertIn('plxscripting', result['error'].lower())

    def test_connection_error_returns_not_executed(self):
        from assistant.plaxis_remote import run_plaxis_problem

        mock_plx = MagicMock()
        mock_plx.new_server.side_effect = ConnectionRefusedError('port closed')

        with patch.dict(sys.modules, {'plxscripting': mock_plx,
                                       'plxscripting.easy': mock_plx}):
            result = run_plaxis_problem('# dummy', version='2d')

        self.assertFalse(result['executed'])

    def test_commit_returns_error_dict_when_not_executed(self):
        app = _make_remote_app()
        plan = {
            'action': 'plaxis_run_problem',
            'version': '2d',
            'problem_type': 'excavation_pit',
            'project_name': 'Test',
            'script': '# dummy',
        }
        with patch('assistant.plaxis_remote.run_plaxis_problem') as mock_run:
            mock_run.return_value = {
                'executed': False,
                'error': 'Không kết nối được Plaxis',
                'output': '',
                'results': {},
            }
            result = app.commit(plan)

        self.assertFalse(result['ok'])
        self.assertIn('Không kết nối được Plaxis', result['error'])

    def test_commit_returns_ok_with_results(self):
        app = _make_remote_app()
        plan = {
            'action': 'plaxis_run_problem',
            'version': '2d',
            'problem_type': 'excavation_pit',
            'project_name': 'Test',
            'script': '# dummy',
        }
        with patch('assistant.plaxis_remote.run_plaxis_problem') as mock_run:
            mock_run.return_value = {
                'executed': True,
                'error': '',
                'output': 'Hoan thanh phan tich ho dao.\nSF = 1.423',
                'results': {
                    'max_settlement_mm': 45.2,
                    'max_horizontal_displacement_mm': 22.1,
                    'safety_factor': 1.423,
                    'phase_results': [{'phase': 'Dao dat', 'max_settlement_mm': 45.2}],
                    'raw_summary': 'Dao dat | Lun max: 45.2 mm | SF: 1.423',
                },
            }
            result = app.commit(plan)

        self.assertTrue(result['ok'])
        self.assertTrue(result['executed'])
        self.assertAlmostEqual(result['max_settlement_mm'], 45.2, places=1)
        self.assertAlmostEqual(result['safety_factor'], 1.423, places=3)
        self.assertIn('45.2', result['note'])
        self.assertIn('1.423', result['note'])


# ── Tool registry tests ───────────────────────────────────────────────────────

class TestToolRegistry(unittest.TestCase):
    def test_plaxis_run_problem_in_extra_tools(self):
        from assistant.tools import EXTRA_TOOLS, WRITES
        names = [t['function']['name'] for _, t in EXTRA_TOOLS]
        self.assertIn('plaxis_run_problem', names)
        self.assertIn('plaxis_run_problem', WRITES)

    def test_plaxis_run_problem_schema_has_required_fields(self):
        from assistant.tools import EXTRA_TOOLS
        schema = next(t for _, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_run_problem')
        fn = schema['function']
        self.assertIn('project_name', fn['parameters']['properties'])
        self.assertIn('version', fn['parameters']['properties'])
        self.assertIn('problem', fn['parameters']['properties'])
        self.assertIn('project_name', fn['parameters']['required'])
        self.assertIn('version', fn['parameters']['required'])
        self.assertIn('problem', fn['parameters']['required'])

    def test_plaxis_remote_module_in_extra_tools(self):
        from assistant.tools import EXTRA_TOOLS
        modules = [m for m, t in EXTRA_TOOLS if t['function']['name'] == 'plaxis_run_problem']
        self.assertEqual(modules, ['plaxis_remote'])


def _find_phase_index(phases_data, phase):
    for i, (p, *_) in enumerate(phases_data):
        if p is phase:
            return i
    return 0


if __name__ == '__main__':
    unittest.main()
