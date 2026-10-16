import io
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from assistant.accounts import AccountAPIError
from assistant.failover import ai_request, active_backup, load_backup, mark_unavailable
from assistant.cloud import ServerApiClient, CloudError, cloud_events
from tests.test_server_api_stream import Response

PRIMARY={'endpoint':'https://primary.example','username':'owner','key':'primary-token'}
BACKUP={'endpoint':'https://backup.example','username':'backup-owner','key':'backup-token'}

class PrimaryOnlyTests(unittest.TestCase):
    def test_outage_never_reads_backup_or_retries_elsewhere(self):
        for path in ['/api/provider/model','/api/models','/api/document/model']:
            with patch('assistant.failover.load_backup',return_value=BACKUP) as saved, patch('assistant.failover.request_account',side_effect=AccountAPIError('down',503)) as request:
                with self.assertRaises(AccountAPIError):ai_request(PRIMARY,path,{'key':'primary-token'})
                self.assertEqual(request.call_count,1)
                self.assertEqual(request.call_args.args[0],PRIMARY['endpoint'])
                saved.assert_not_called()

    def test_saved_backup_and_circuit_state_are_inert(self):
        mark_unavailable(PRIMARY)
        self.assertIsNone(active_backup(PRIMARY))
        self.assertIsNone(load_backup(PRIMARY))

    def test_stream_outage_never_fails_over(self):
        error=HTTPError(PRIMARY['endpoint'],503,'down',{},io.BytesIO(b'{}'))
        with patch('assistant.failover.load_backup',return_value=BACKUP) as saved,patch('assistant.cloud.urlopen',side_effect=error) as request:
            with self.assertRaises(CloudError):list(ServerApiClient(PRIMARY,'nvidia').stream_answer('nvidia',[]))
            self.assertEqual(request.call_count,1);saved.assert_not_called()
            self.assertIn('primary.example',request.call_args.args[0].full_url)

    def test_partial_stream_never_replayed(self):
        with patch('assistant.cloud.urlopen',return_value=Response(b'data: {"choices":[{"delta":{"content":"part"}}]}\n')) as request:
            stream=ServerApiClient(PRIMARY,'nvidia').stream_answer('nvidia',[])
            self.assertEqual(next(stream),('text','part'))
            with self.assertRaises(CloudError):next(stream)
            self.assertEqual(request.call_count,1)

    def test_cloudflare_outage_never_retries_backup(self):
        error=HTTPError(PRIMARY['endpoint'],503,'down',{},io.BytesIO(b'{}'))
        opener=Mock(side_effect=error)
        with patch('assistant.failover.load_backup',return_value=BACKUP) as saved:
            with self.assertRaises(CloudError):list(cloud_events(PRIMARY['endpoint'],{'username':'owner','key':'primary-token'},opener))
            self.assertEqual(opener.call_count,1);saved.assert_not_called()

    def test_chat_and_stream_ignore_saved_custom_direct_configuration(self):
        with patch('assistant.custom_backup_api.load',return_value={'use_direct':True}) as custom,patch('assistant.failover.ai_request',return_value={'success':True,'answer':'OK'}) as request:
            self.assertEqual(ServerApiClient(PRIMARY,'nvidia').chat('nvidia',[])['message']['content'],'OK')
            self.assertEqual(request.call_args.args[0],PRIMARY);custom.assert_not_called()
        data=b'data: {"choices":[{"delta":{"content":"OK"}}]}\ndata: [DONE]\n'
        with patch('assistant.custom_backup_api.load',return_value={'use_direct':True}) as custom,patch('assistant.cloud.urlopen',return_value=Response(data)) as request:
            self.assertEqual(list(ServerApiClient(PRIMARY,'nvidia').stream_answer('nvidia',[])),[('text','OK')])
            self.assertIn('primary.example',request.call_args.args[0].full_url);custom.assert_not_called()
