import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from assistant.accounts import AccountAPIError
from assistant.failover import ai_request, _unavailable
from assistant.cloud import ServerApiClient, CloudError
from tests.test_server_api_stream import Response

PRIMARY={'endpoint':'https://primary.example','username':'owner','key':'primary-token'}
BACKUP={'endpoint':'https://backup.example','username':'backup-owner','key':'backup-token'}

class FailoverTests(unittest.TestCase):
    def setUp(self):_unavailable.clear()
    def test_outage_uses_only_backup_credentials_and_circuits_later_requests(self):
        with patch('assistant.failover.load_backup',return_value=BACKUP), patch('assistant.failover.request_account',side_effect=[AccountAPIError('D1 limit',503),{'success':True},{'success':True}]) as request:
            ai_request(PRIMARY,'/api/provider/model',{'username':'owner','key':'primary-token'})
            ai_request(PRIMARY,'/api/provider/model',{'username':'owner','key':'primary-token'})
            self.assertEqual(request.call_args_list[1].args[0],BACKUP['endpoint'])
            self.assertEqual(request.call_args_list[1].args[2]['key'],'backup-token')
            self.assertEqual(request.call_args_list[2].args[0],BACKUP['endpoint'])
    def test_auth_billing_and_writes_do_not_fail_over(self):
        for path,error in [('/api/provider/model',AccountAPIError('denied',401)),('/api/provider/model',AccountAPIError('billing',429,code='QUOTA_EXHAUSTED')),('/api/conversations/append',AccountAPIError('down',503))]:
            with patch('assistant.failover.load_backup',return_value=BACKUP),patch('assistant.failover.request_account',side_effect=error) as request:
                with self.assertRaises(AccountAPIError):ai_request(PRIMARY,path,{'key':'primary-token'})
                self.assertEqual(request.call_count,1)
    def test_stream_switches_before_output(self):
        error=HTTPError(PRIMARY['endpoint'],503,'down',{},io.BytesIO(b'{}'))
        with patch('assistant.failover.load_backup',return_value=BACKUP),patch('assistant.cloud.urlopen',side_effect=[error,Response(b'data: {"choices":[{"delta":{"content":"OK"}}]}\ndata: [DONE]\n')]) as request:
            self.assertEqual(list(ServerApiClient(PRIMARY,'nvidia').stream_answer('nvidia',[])),[('text','OK')])
            self.assertIn('backup.example',request.call_args.args[0].full_url)
            self.assertNotIn(b'primary-token',request.call_args.args[0].data)
    def test_partial_stream_never_replayed(self):
        with patch('assistant.failover.load_backup',return_value=BACKUP),patch('assistant.cloud.urlopen',return_value=Response(b'data: {"choices":[{"delta":{"content":"part"}}]}\n')) as request:
            stream=ServerApiClient(PRIMARY,'nvidia').stream_answer('nvidia',[])
            self.assertEqual(next(stream),('text','part'))
            with self.assertRaises(CloudError):next(stream)
            self.assertEqual(request.call_count,1)

    def test_cloudflare_chat_uses_backup_before_events(self):
        from assistant.cloud import cloud_events
        error=HTTPError(PRIMARY['endpoint'],503,'down',{},io.BytesIO(b'{}'))
        with patch('assistant.failover.load_backup',return_value=BACKUP),patch('assistant.cloud.urlopen'):
            opener=__import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=[error,Response(b'event: delta\ndata: {"text":"OK"}\n\n')])
            events=list(cloud_events(PRIMARY['endpoint'],dict(username='owner',key='primary-token',text='Hi'),opener))
            self.assertEqual(events[-1],('delta',{'text':'OK'}))
            self.assertIn('backup.example',opener.call_args.args[0].full_url)
            self.assertNotIn(b'primary-token',opener.call_args.args[0].data)
