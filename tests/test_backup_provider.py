import unittest
from unittest.mock import patch
from assistant.backup_provider import backup_provider_request

SESSION={'endpoint':'https://backup.example','username':'backup-admin','key':'backup-token'}
class BackupProviderTests(unittest.TestCase):
    def test_openrouter_save_targets_backup_with_its_own_key_and_model(self):
        with patch('assistant.backup_provider.request_account',return_value={'success':True}) as call:
            backup_provider_request(SESSION,'save','openrouter','backup-router-key','vendor/model:free')
            endpoint,path,body=call.call_args.args
            self.assertEqual(endpoint,SESSION['endpoint'])
            self.assertEqual(path,'/api/admin/providers/save')
            self.assertEqual(body['providers'],{'openrouter':'backup-router-key'})
            self.assertEqual(body['models'],{'openrouter':'vendor/model:free'})

    def test_visible_server_choices_preserve_current_and_exclude_primary(self):
        from assistant.backup_provider import backup_server_choices
        primary='https://chatai.anhvn53.workers.dev/'
        result=backup_server_choices(primary,'https://custom-backup.example/')
        self.assertEqual(result[0],'https://custom-backup.example')
        self.assertIn('https://chatai-backup.vuanh97nd1.workers.dev',result)
        self.assertNotIn(primary.rstrip('/'),result)
        self.assertNotIn('https://user:secret@example.org',backup_server_choices(primary,'https://user:secret@example.org'))
    def test_models_catalog_only_addresses_backup_and_reuses_stored_provider_key(self):
        with patch('assistant.backup_provider.request_account',return_value={'success':True,'models':['nvidia/model-a','nvidia/model-b']}) as call:
            result=backup_provider_request(SESSION,'models','nvidia')
            endpoint,path,body=call.call_args.args
            self.assertEqual(endpoint,'https://backup.example')
            self.assertEqual(path,'/api/admin/providers/models')
            self.assertEqual(body['provider'],'nvidia')
            self.assertEqual(body['api_key'],'')
            self.assertNotIn('model',body)
            self.assertEqual(len(result['models']),2)
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
