import unittest
from assistant.conversation_context import conversation_context
from assistant.prompts import FAST_SYSTEM

class ContextTests(unittest.TestCase):
    def test_recalls_prior_choices_outside_recent_turns(self):
        rows=[{'role':'user','content':'Đơn vị m, font Times New Roman cỡ 13.'}]+[{'role':'assistant','content':'Trả lời '+str(i)} for i in range(45)]
        result=conversation_context(rows)
        self.assertIn('font Times New Roman',result[0]['content'])
        self.assertLessEqual(len(result),121)  # limits raised on request: up to 120 recent turns
        self.assertIn('Trả lời 44',result[-1]['content'])
    def test_answer_is_not_cut_at_1600_characters(self):
        text='x'*2000+'Thông tin đã chốt'
        self.assertEqual(conversation_context([{'role':'assistant','content':text}])[0]['content'],text)
    def test_cloudflare_budget_and_topic_rule(self):
        result=conversation_context([{'role':'user','content':'x'*6000} for _ in range(30)],online=False)
        self.assertLessEqual(sum(len(m['content']) for m in result),30000)  # offline budget raised to 30000
        self.assertIn('chuyển chủ đề',FAST_SYSTEM)
