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
