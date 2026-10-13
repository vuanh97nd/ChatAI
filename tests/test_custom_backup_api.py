import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from assistant.custom_backup_api import endpoint_url, chat, stream_answer, load, save
from assistant.accounts import AccountAPIError
from assistant.failover import ai_request
from assistant.cloud import ServerApiClient


class Response(io.BytesIO):
    def __init__(self, value, content_type='application/json'):
        super().__init__(value)
        self.headers = {'Content-Type': content_type}


class CustomBackupTests(unittest.TestCase):
    profile = {'url': 'http://127.0.0.1:3040', 'model': 'test-model', 'api_key': 'server-secret', 'enabled': True}
    primary = {'endpoint': 'https://main.example', 'username': 'owner', 'key': 'main-secret'}

    def test_url_normalization_and_transport(self):
        for url in ['http://127.0.0.1:3040', 'http://127.0.0.1:3040/v1', 'http://127.0.0.1:3040/v1/chat/completions']:
            self.assertEqual(endpoint_url(url), 'http://127.0.0.1:3040/v1/chat/completions')
        for url in ['http://vps.example', 'https://user:secret@vps.example', 'https://vps.example?key=secret']:
            with self.assertRaises(ValueError): endpoint_url(url)

    def test_request_does_not_forward_chat_ai_credentials(self):
        opener = Mock()
        opener.open.return_value = Response(b'{"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}]}')
        with patch('assistant.custom_backup_api.build_opener', return_value=opener):
            self.assertEqual(chat(self.profile, [{'role': 'user', 'content': 'Hi'}])['answer'], 'OK')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer server-secret')
        payload = json.loads(request.data)
        self.assertNotIn('key', payload)
        self.assertNotIn('username', payload)
        self.assertEqual(payload['model'], 'test-model')

    def test_http_error_does_not_echo_key(self):
        opener = Mock()
        opener.open.side_effect = HTTPError('https://api.example', 401, 'server-secret', {}, io.BytesIO(b'server-secret'))
        with patch('assistant.custom_backup_api.build_opener', return_value=opener):
            with self.assertRaises(RuntimeError) as caught: chat(self.profile, [])
        self.assertNotIn('server-secret', str(caught.exception))

    def test_partial_stream_reports_failure_without_replay(self):
        data = b'data: {"choices":[{"delta":{"content":"part"}}]}\n'
        with patch('assistant.custom_backup_api.open_response', return_value=Response(data, 'text/event-stream')) as call:
            iterator = stream_answer(self.profile, [])
            self.assertEqual(next(iterator), ('text', 'part'))
            with self.assertRaises(RuntimeError): next(iterator)
            self.assertEqual(call.call_count, 1)

    def test_json_failover_only_for_provider_outages(self):
        with patch('assistant.failover.active_backup', return_value=None), patch('assistant.failover.load_backup', return_value=None), patch('assistant.failover.request_account', side_effect=AccountAPIError('down', 503)), patch('assistant.custom_backup_api.fallback', return_value={'success': True, 'answer': 'OK'}) as call:
            self.assertEqual(ai_request(self.primary, '/api/provider/model', {'messages': []})['answer'], 'OK')
            self.assertEqual(call.call_args.args[0], self.primary)
        for error in [AccountAPIError('denied', 401), AccountAPIError('billing', 429, code='QUOTA_EXHAUSTED')]:
            with patch('assistant.failover.active_backup', return_value=None), patch('assistant.failover.load_backup', return_value=None), patch('assistant.failover.request_account', side_effect=error), patch('assistant.custom_backup_api.fallback') as call:
                with self.assertRaises(AccountAPIError): ai_request(self.primary, '/api/provider/model', {'messages': []})
                call.assert_not_called()

    def test_direct_chat_skips_worker_and_preserves_json_instruction(self):
        profile = dict(self.profile, use_direct=True)
        with patch('assistant.failover.active_backup', return_value=None), patch('assistant.custom_backup_api.load', return_value=profile), patch('assistant.custom_backup_api.chat', return_value={'success':True,'answer':'{"tool":""}'}) as request, patch('assistant.failover.ai_request') as remote:
            client=ServerApiClient(self.primary,'nvidia')
            result=client.chat('nvidia',[{'role':'user','content':'task'}],format={'type':'object'})
            self.assertEqual(result['message']['content'],'{"tool":""}')
            self.assertIn('JSON schema', request.call_args.args[1][0]['content'])
            remote.assert_not_called()

    def test_chat_keeps_original_scope_when_worker_backup_is_active(self):
        backup={'endpoint':'https://backup.example','username':'other','key':'backup-key'}
        with patch('assistant.failover.active_backup',return_value=backup), patch('assistant.custom_backup_api.load',return_value=None) as load_config, patch('assistant.failover.ai_request',return_value={'success':True,'answer':'OK'}) as request:
            client=ServerApiClient(self.primary,'nvidia')
            client.chat('nvidia',[])
            self.assertEqual(load_config.call_args.args[0],{k:self.primary[k] for k in ('endpoint','username')})
            self.assertEqual(request.call_args.args[0],self.primary)
            self.assertEqual(request.call_args.args[2]['key'],'main-secret')

    def test_node_precedes_worker_backup_after_outage(self):
        with patch('assistant.failover.active_backup',return_value=None), patch('assistant.failover.load_backup',return_value={'endpoint':'https://backup.example','username':'other','key':'backup-key'}), patch('assistant.failover.request_account',side_effect=AccountAPIError('busy',503)) as worker, patch('assistant.custom_backup_api.fallback',return_value={'success':True,'answer':'Node OK'}):
            self.assertEqual(ai_request(self.primary,'/api/provider/model',{'messages':[]})['answer'],'Node OK')
            self.assertEqual(worker.call_count,1)

    def test_direct_stream_does_not_contact_worker(self):
        with patch('assistant.failover.active_backup',return_value=None), patch('assistant.custom_backup_api.load',return_value=dict(self.profile,use_direct=True)), patch('assistant.custom_backup_api.stream_answer',return_value=iter([('text','OK')])) as stream, patch('assistant.cloud.urlopen') as worker:
            self.assertEqual(list(ServerApiClient(self.primary,'nvidia').stream_answer('nvidia',[])),[('text','OK')])
            stream.assert_called_once()
            worker.assert_not_called()


if __name__ == '__main__': unittest.main()
