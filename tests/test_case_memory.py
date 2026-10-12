"""Tests for case_memory: structured engineering case storage."""
import json
import tempfile
import unittest
from pathlib import Path

from assistant.case_memory import CaseMemory, _extract_results, _extract_soil_params, _detect_problem_type
from assistant.storage import Store


class CaseMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'a.db')
        self.cm = CaseMemory(self.store)

    def test_save_and_search_by_keyword(self):
        self.cm.save('alice', 'slope_stability', 'PLAXIS 2D',
                     'Ổn định mái dốc, phi=25, c=15, FS=1.45',
                     soil_params={'phi': 25, 'c': 15},
                     results={'fs': 1.45})
        results = self.cm.search('alice', 'ổn định mái dốc')
        self.assertEqual(len(results), 1)
        self.assertIn('slope_stability', results[0]['problem_type'])
        self.assertAlmostEqual(results[0]['results']['fs'], 1.45)

    def test_isolation_between_owners(self):
        self.cm.save('alice', 'settlement', 'PLAXIS 2D', 'Tính lún, gamma=18')
        self.assertEqual(self.cm.search('bob', 'lún'), [])

    def test_no_match_unrelated_query(self):
        self.cm.save('alice', 'foundation', 'GeoSlope', 'Sức chịu tải móng')
        self.assertEqual(self.cm.search('alice', 'thời tiết hôm nay'), [])

    def test_capture_from_plaxis_tool_result(self):
        state = {
            'account_username': 'alice',
            'messages': [{'role': 'user', 'content': 'Tính ổn định mái dốc PLAXIS 2D'}],
        }
        call = {'function': {'name': 'plaxis_commands', 'arguments': {'version': '2d', 'phi': 25}}}
        result = {'ok': True, 'factor_of_safety': 1.35}
        self.cm.capture('alice', state, call, result)
        cases = self.cm.search('alice', 'mái dốc PLAXIS')
        self.assertEqual(len(cases), 1)
        self.assertIn('PLAXIS', cases[0]['software'])

    def test_capture_skips_failed_result(self):
        state = {'account_username': 'alice', 'messages': []}
        call = {'function': {'name': 'plaxis_commands', 'arguments': {}}}
        self.cm.capture('alice', state, call, {'ok': False, 'error': 'lỗi'})
        self.assertEqual(self.cm.search('alice', 'plaxis'), [])

    def test_capture_skips_non_calculation_tool(self):
        state = {'account_username': 'alice', 'messages': []}
        call = {'function': {'name': 'word_create_open', 'arguments': {}}}
        self.cm.capture('alice', state, call, {'ok': True})
        self.assertEqual(self.cm.search('alice', 'word'), [])

    def test_list_cases(self):
        self.cm.save('alice', 'tunnel', 'PLAXIS 3D', 'Đường hầm')
        self.cm.save('alice', 'slope_stability', 'GeoSlope', 'Mái dốc')
        cases = self.cm.list_cases('alice')
        self.assertEqual(len(cases), 2)

    def test_delete(self):
        ident = self.cm.save('alice', 'foundation', 'PLAXIS', 'Móng')
        self.cm.delete('alice', ident)
        self.assertEqual(self.cm.list_cases('alice'), [])

    def test_context_returns_empty_when_no_match(self):
        self.assertEqual(self.cm.context('alice', 'câu hỏi vô nghĩa xyz'), '')

    def test_extract_soil_params(self):
        args = {'gamma': 18.0, 'phi': 25.0, 'cohesion': 15.0, 'password': 'secret'}
        params = _extract_soil_params(args)
        self.assertIn('gamma', params)
        self.assertIn('phi', params)
        self.assertNotIn('password', params)

    def test_extract_results(self):
        result = {'ok': True, 'factor_of_safety': 1.5, 'settlement': 12.3}
        r = _extract_results(result)
        self.assertIn('factor_of_safety', r)
        self.assertIn('settlement', r)

    def test_detect_problem_type(self):
        self.assertEqual(_detect_problem_type('tính ổn định mái dốc', {}, {}), 'slope_stability')
        self.assertEqual(_detect_problem_type('tính lún nền', {}, {}), 'settlement')
        self.assertEqual(_detect_problem_type('tính móng cọc', {}, {}), 'foundation')


class CaseMemoryPersistenceTest(unittest.TestCase):
    def test_survives_store_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'db.sqlite'
            store = Store(path)
            CaseMemory(store).save('alice', 'slope_stability', 'PLAXIS',
                                   'Ổn định đất sét mềm, phi=20, c=10')
            store2 = Store(path)
            results = CaseMemory(store2).search('alice', 'đất sét mềm')
            self.assertEqual(len(results), 1)
