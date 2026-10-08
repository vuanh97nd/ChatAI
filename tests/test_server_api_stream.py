import io,json,unittest
from urllib.error import HTTPError
from email.message import Message
from unittest.mock import patch
from assistant.cloud import ServerApiClient,CloudError

class Response(io.BytesIO):
    def __init__(self,data,content_type='text/event-stream'):
        super().__init__(data);self.headers=Message();self.headers['Content-Type']=content_type

class ServerStreamingTest(unittest.TestCase):
    def test_yields_first_answer_chunk_without_consuming_rest(self):
        response=Response(b'data: {"choices":[{"delta":{"reasoning_content":"hidden"}}]}\n\ndata: {"choices":[{"delta":{"content":"Xin "}}]}\n\ndata: {"choices":[{"delta":{"content":"chao"}}]}\n\ndata: [DONE]\n\n')
        client=ServerApiClient({'endpoint':'https://example.com','username':'admin','key':'test-session'},'deepseek_flash')
        seen=[]
        def open_request(request,timeout):
            self.assertEqual(request.get_header('User-agent'),'ChatAI-Desktop/2.5 (+Windows; account API)')
            seen.append(json.loads(request.data));return response
        with patch('assistant.cloud.urlopen',open_request),patch('assistant.performance.record') as timing:
            stream=client.stream_answer(client.model,[{'role':'user','content':'Chao'}])
            self.assertEqual(next(stream),('reasoning','hidden'))
            self.assertEqual(next(stream),('text','Xin '))
            self.assertLess(response.tell(),len(response.getvalue()))
            self.assertEqual(list(stream),[('text','chao')])
        self.assertTrue(seen[0]['stream']);self.assertEqual(seen[0]['provider'],'deepseek_flash')
        self.assertEqual([c.args[0] for c in timing.call_args_list],['ai.wait_response_headers','ai.wait_first_text_stream','ai.request_total'])
    def test_old_worker_json_reply_remains_compatible(self):
        response=Response(b'{"success":true,"answer":"OK"}','application/json')
        client=ServerApiClient({'endpoint':'https://example.com','username':'admin','key':'test-session'},'deepseek')
        with patch('assistant.cloud.urlopen',return_value=response):self.assertEqual(list(client.stream_answer(client.model,[])),[('text','OK')])

    def test_forbidden_worker_response_explains_source_and_hides_session(self):
        client=ServerApiClient({'endpoint':'https://example.com','username':'admin','key':'test-session'},'deepseek')
        for data in [b'<html>Forbidden</html>',b'{"message":"denied test-session"}',b'[]']:
            error=HTTPError('https://example.com/api/provider/model',403,'Forbidden',{},io.BytesIO(data))
            with patch('assistant.cloud.urlopen',side_effect=error),self.assertRaises(CloudError) as caught:
                list(client.stream_answer(client.model,[]))
            self.assertIn('Worker',str(caught.exception));self.assertNotIn('test-session',str(caught.exception))
