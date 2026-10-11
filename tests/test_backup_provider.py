import unittest
from unittest.mock import patch
from assistant.backup_provider import backup_provider_request

SESSION={'endpoint':'https://backup.example','username':'backup-admin','key':'backup-token'}
class BackupProviderTests(unittest.TestCase):
    def test_save_only_to_backup_and_blank_key_keeps_previous_key(self):
        with patch('assistant.backup_provider.request_account',return_value={'success':True}) as call:
            backup_provider_request(SESSION,'save','deepseek',model='deepseek-flash')
            endpoint,path,body=call.call_args.args
            self.assertEqual(endpoint,'https://backup.example')
            self.assertEqual(path,'/api/admin/providers/save')
            self.assertEqual(body['providers'],{})
            self.assertEqual(body['models'],{'deepseek':'deepseek-flash'})
            self.assertEqual(body['key'],'backup-token')
    def test_cloudflare_test_calls_real_ai_without_admin_key_configuration(self):
        with patch('assistant.backup_provider.request_account',return_value={'success':True,'answer':'OK'}) as call:
            backup_provider_request(SESSION,'test','cloudflare')
            self.assertEqual(call.call_args.args[1],'/api/provider/model')
            self.assertEqual(call.call_args.args[2]['provider'],'cloudflare')
            self.assertNotIn('api_key',call.call_args.args[2])
    def test_save_rejects_invalid_input_before_network(self):
        with patch('assistant.backup_provider.request_account') as call:
            for provider,key,model in [('cloudflare','','x'),('deepseek','short','x'),('deepseek','','bad model')]:
                with self.assertRaises(ValueError):backup_provider_request(SESSION,'save',provider,key,model)
            call.assert_not_called()
    def test_failed_write_is_not_retried_and_key_redacted(self):
        secret='private-secret-api-key'
        with patch('assistant.backup_provider.request_account',side_effect=RuntimeError('failure '+secret)) as call:
            with self.assertRaisesRegex(RuntimeError,'\\[ẨN\\]'):
                backup_provider_request(SESSION,'save','deepseek',secret)
            self.assertEqual(call.call_count,1)
