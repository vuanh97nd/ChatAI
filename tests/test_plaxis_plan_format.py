import json
import unittest
from assistant.online_automation import parse_plan
from assistant.tools import EXTRA_TOOLS
from assistant.plaxis_app import _validate_problem

class PlaxisPlanFormatTests(unittest.TestCase):
    def test_problem_object_is_normalized_for_both_tools(self):
        for tool in ('plaxis_run_problem','plaxis_generate_script'):
            for encoded_arguments in (False,True):
                args={'version':'2d','project_name':'BoDap','problem':{'type':'embankment_stability','embankment_height':4}}
                raw=json.dumps({'tool':tool,'arguments':json.dumps(args) if encoded_arguments else args})
                plan=parse_plan(raw,[spec for _,spec in EXTRA_TOOLS])
                self.assertIsInstance(plan['arguments']['problem'],str)
                self.assertEqual(_validate_problem(plan['arguments']['problem'])['embankment_height'],4)
    def test_existing_problem_string_is_preserved(self):
        problem=json.dumps({'type':'embankment_stability'})
        raw=json.dumps({'tool':'plaxis_run_problem','arguments':{'version':'2d','project_name':'BoDap','problem':problem}})
        self.assertEqual(parse_plan(raw,[spec for _,spec in EXTRA_TOOLS])['arguments']['problem'],problem)
    def test_non_object_invalid_problem_is_still_rejected(self):
        for problem in ([],42,None):
            raw=json.dumps({'tool':'plaxis_run_problem','arguments':{'version':'2d','project_name':'BoDap','problem':problem}})
            with self.assertRaises((ValueError,TypeError)):parse_plan(raw,[spec for _,spec in EXTRA_TOOLS])
