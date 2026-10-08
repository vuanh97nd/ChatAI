import unittest
from unittest.mock import patch
from assistant.cloud import ServerApiClient
from assistant.accounts import AccountAPIError

class ResponseRepairTests(unittest.TestCase):
    def test_empty_reply_recovers_once_without_reexecuting_a_tool(self):
        seen=[]
        def request(endpoint,path,body,**kw):
            seen.append(dict(body))
            if len(seen)==1:raise AccountAPIError('empty',502,code='EMPTY_AI_RESPONSE')
            return {'success':True,'answer':'Đã nhận thông tin'}
        client=ServerApiClient({'endpoint':'https://example.org','username':'alice','key':'fake'},'deepseek_flash')
        with patch('assistant.accounts.request_account',request):answer=client.chat('deepseek_flash',[{'role':'user','content':'Hãy sửa lỗi'}])
        self.assertEqual(answer['message']['content'],'Đã nhận thông tin')
        self.assertEqual(len(seen),2);self.assertTrue(seen[1]['repair_response'])
    def test_does_not_loop_or_retry_content_filter(self):
        client=ServerApiClient({'endpoint':'https://example.org','username':'alice','key':'fake'},'deepseek_flash')
        for code,count in [('EMPTY_AI_RESPONSE',2),('AI_CONTENT_FILTER',1)]:
            with patch('assistant.accounts.request_account',side_effect=AccountAPIError('error',502,code=code)) as request:
                with self.assertRaises(AccountAPIError):client.chat('deepseek_flash',[{'role':'user','content':'test'}])
                self.assertEqual(request.call_count,count)
