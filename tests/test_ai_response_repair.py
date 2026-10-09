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

class DroppedConnectionTests(unittest.TestCase):
    def setUp(self):
        self.client=ServerApiClient({'endpoint':'https://example.org','username':'alice','key':'fake'},'deepseek_flash')
        self.client.cancel_event=None

    def test_model_request_retries_after_the_server_drops_the_connection(self):
        from assistant.accounts import AccountConnectionError
        calls=[]
        def request(endpoint,path,body,**kw):
            calls.append(path)
            if len(calls)==1:raise AccountConnectionError('dropped')
            return {'success':True,'answer':'Tiếp tục dựng mô hình'}
        with patch('assistant.accounts.request_account',request),patch('threading.Event.wait',return_value=False):
            answer=self.client.chat('deepseek_flash',[{'role':'user','content':'PLAXIS'}])
        self.assertEqual(answer['message']['content'],'Tiếp tục dựng mô hình')
        self.assertEqual(len(calls),2)

    def test_repeated_drops_end_with_a_clear_error_instead_of_a_raw_socket_message(self):
        from assistant.accounts import AccountConnectionError
        from assistant.cloud import CloudError
        with patch('assistant.accounts.request_account',side_effect=AccountConnectionError('dropped')) as request,\
             patch('threading.Event.wait',return_value=False):
            with self.assertRaises(CloudError) as caught:self.client.chat('deepseek_flash',[{'role':'user','content':'x'}])
        self.assertEqual(request.call_count,3)
        self.assertNotIn('Remote end',str(caught.exception))

    def test_request_account_reports_a_dropped_connection_as_retryable(self):
        from http.client import RemoteDisconnected
        from assistant.accounts import AccountConnectionError,request_account
        with patch('assistant.accounts.urlopen',side_effect=RemoteDisconnected('Remote end closed connection without response')):
            with self.assertRaises(AccountConnectionError):
                request_account('https://example.org','/api/provider/model',{'key':'k'})
