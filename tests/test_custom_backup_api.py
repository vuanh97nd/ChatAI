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

    def test_legacy_custom_configuration_is_not_loaded(self):
        with patch('assistant.custom_backup_api._dpapi') as decrypt:
            self.assertIsNone(load({'endpoint':'https://main.example','username':'owner'}))
            decrypt.assert_not_called()


if __name__ == '__main__': unittest.main()
