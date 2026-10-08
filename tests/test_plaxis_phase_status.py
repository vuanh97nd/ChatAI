import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from assistant.plaxis_remote import phase_diagnostics,run_plaxis_problem
from assistant.plaxis_app import _generate_script,_validate_problem
from tests.test_plaxis_ai import SLOPE_PROBLEM

class PhaseStatusTests(unittest.TestCase):
    def test_status_reads_remote_value_and_failure_log(self):
        phase=SimpleNamespace(Identification='Safety',CalculationResult=SimpleNamespace(value=2),LogInfo=SimpleNamespace(value='Soil body collapses'))
        rows=phase_diagnostics(SimpleNamespace(Phases=[phase]))
        self.assertEqual(rows,[{'name':'Safety','status':2,'log':'Soil body collapses'}])
    def test_red_phase_is_not_reported_as_success(self):
        phase=SimpleNamespace(Identification='Phase_1',CalculationResult=2,LogInfo='Reached step 30; calculation failed')
        g=SimpleNamespace(Phases=[phase]);server=SimpleNamespace(new=lambda:None)
        with patch('assistant.plaxis_remote._connect',return_value=(server,g)),patch('assistant.plaxis_remote._exec_script_on_server',return_value='returned without exception'):
            result=run_plaxis_problem('# script','2d','slope_stability')
        self.assertFalse(result['executed'])
        self.assertIn('step 30',result['error'])
    def test_slope_phase_uses_safety_not_bishop_claim(self):
        script=_generate_script(_validate_problem(SLOPE_PROBLEM),'2d',10000,'Test')
        self.assertIn('DeformCalcType.enumeration.PhiCReduction',script)
        self.assertNotIn('Hoan thanh phan tich on dinh mai doc bang Bishop',script)
        self.assertIn('Safety (c-phi reduction)',script)
