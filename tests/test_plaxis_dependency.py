import unittest
from unittest.mock import patch
from assistant.plaxis_dependency import missing_scripting_message
from assistant.modules import MODULES

class PlaxisDependencyTests(unittest.TestCase):
    def test_reports_running_interpreter_and_correct_import_check(self):
        with patch('sys.executable','G:/Chat AI/runtime/python/pythonw.exe'):
            value=missing_scripting_message()
        self.assertIn("& 'G:/Chat AI/runtime/python/python.exe' -m pip install",value)
        self.assertIn('plxscripting.__file__',value)
        self.assertEqual(MODULES['plaxis']['imports'],['plxscripting'])
    def test_frozen_executable_is_not_used_as_pip_interpreter(self):
        with patch('sys.frozen',True,create=True):value=missing_scripting_message()
        self.assertNotIn('-m pip',value)
        self.assertIn('bộ cài',value)
