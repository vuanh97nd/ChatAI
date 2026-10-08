import json
import unittest

from assistant.online_automation import discussion_response, parse_plan
from assistant.tools import EXTRA_TOOLS


class PlanRecoveryTests(unittest.TestCase):
    def setUp(self):self.schemas=[spec for _,spec in EXTRA_TOOLS]

    def test_bom_and_explanatory_fence_preserve_validated_call(self):
        plan={'answer':'','tool':'windows_open','arguments':{'path':'C:/Apps/word.exe'}}
        for raw in ('\ufeff'+json.dumps(plan), 'Kế hoạch:\n```json\n'+json.dumps(plan)+'\n```'):
            self.assertEqual(parse_plan(raw,self.schemas)['arguments'],plan['arguments'])

    def test_multiple_or_truncated_objects_are_not_executed(self):
        for raw in ('Kế hoạch: {} {}', '{"answer":"x","arguments":{"path":"C:/x"}',
                    'Kế hoạch: {"tool":"unregistered_tool","arguments":{"command":"bad"}}'):
            with self.assertRaises(ValueError):parse_plan(raw,self.schemas)

    def test_distinct_errors_identify_outer_or_nested_json(self):
        with self.assertRaisesRegex(ValueError,'Phản hồi kế hoạch đang rỗng'):
            parse_plan(' ',self.schemas)
        with self.assertRaisesRegex(ValueError,'Tham số arguments không phải JSON'):
            parse_plan(json.dumps({'answer':'x','arguments':'not JSON'}),self.schemas)
        self.assertEqual(parse_plan('{"answer":"Bạn cần hỗ trợ gì?","arguments":"   "}',self.schemas)['arguments'],{})

    def test_only_plain_clarification_is_recovered(self):
        self.assertIn('chưa thực hiện',discussion_response('Bạn cho biết chiều dài mô hình là bao nhiêu?'))
        for text in ('Đã chạy và hoàn tất bài toán.', '{"tool":"bad"}', '```python\nrun()\n```', '',
                     'Đã mở Word. Bạn cần gì thêm?'):
            self.assertIsNone(discussion_response(text))

    def test_single_plan_array_wrappers_and_encoded_json_preserve_arguments(self):
        plan={'answer':'','tool':'windows_open','arguments':{'path':'C:/Apps/word.exe'}}
        for value in ([plan], {'plan':plan}, {'response':[plan]},json.dumps(plan),
                      {'tool_calls':[{'function':{'name':plan['tool'],'arguments':plan['arguments']}}]},
                      {'tool_calls':[{'name':plan['tool'],'arguments':plan['arguments']}]},
                      {'function':{'name':plan['tool'],'arguments':plan['arguments']}},
                      {'name':plan['tool'],'arguments':plan['arguments']}):
            parsed=parse_plan(json.dumps(value),self.schemas)
            self.assertEqual(parsed['tool'],plan['tool'])
            self.assertEqual(parsed['arguments'],plan['arguments'])

    def test_multiple_plans_and_non_plan_json_are_rejected_without_guessing(self):
        plan={'tool':'windows_open','arguments':{'path':'C:/Apps/word.exe'}}
        for value in ([],[plan,plan],True,None,42,{'plan':plan,'result':plan},
                      {'command':'calculate','args':[]},
                      {'tool_calls':[{'function':{'name':'windows_open'}},{'function':{'name':'windows_open'}}]}):
            with self.assertRaisesRegex(ValueError,'Phản hồi kế hoạch'):
                parse_plan(json.dumps(value),self.schemas)

    def test_wrapping_does_not_bypass_tool_or_parameter_validation(self):
        for plan in ({'tool':'unknown_tool','arguments':{}},
                     {'tool':'windows_open','arguments':{'path':42}}):
            with self.assertRaises(ValueError):parse_plan(json.dumps([plan]),self.schemas)
