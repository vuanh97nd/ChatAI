import unittest

from assistant.model_identity import model_identity_text


class ModelIdentityTests(unittest.TestCase):
    def test_configured_name_is_visible_without_claiming_server_verification(self):
        cfg={'nvidia_model':'nvidia/nemotron-3-super-120b-a12b','server_url':'https://main.example'}
        text=model_identity_text('NVIDIA AI','nvidia',cfg)
        assert 'nvidia/nemotron-3-super-120b-a12b' in text
        assert 'Model trong Cài đặt' in text
        assert 'https://main.example' in text


    def test_backup_does_not_display_primary_model_as_its_model(self):
        cfg={'nvidia_model':'primary/model','server_url':'https://main.example'}
        text=model_identity_text('NVIDIA AI','nvidia',cfg,'https://backup.example',True)
        assert 'primary/model' not in text
        assert 'chưa đọc được' in text
        text=model_identity_text('NVIDIA AI','nvidia',cfg,'https://backup.example',True,{'nvidia':'backup/model'})
        assert 'backup/model' in text and 'Model trên server' in text


    def test_named_profiles_and_local_models_preserve_their_identity(self):
        cfg={'custom_ai':[{'id':'ai_123','model':'deepseek/model'}]}
        assert 'deepseek/model' in model_identity_text('AI thiết kế','ai_123',cfg)
        assert model_identity_text('qwen2.5:7b','local',cfg)=='Model: qwen2.5:7b · AI trên máy'


    def test_deepseek_variant_does_not_take_generic_deepseek_model(self):
        assert 'deepseek-flash' in model_identity_text('DeepSeek Flash','deepseek_flash',{'deepseek_model':'other'})
