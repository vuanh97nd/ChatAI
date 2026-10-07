import unittest
from assistant.hardware_profile import inferred_level,recommendations,available_choice

class HardwareProfiles(unittest.TestCase):
    def test_rtx3070_16gb_is_medium(self):
        self.assertEqual(inferred_level({'ram_gb':16,'vram_gb':8}),'medium')
    def test_cpu_8gb_is_weak(self):
        self.assertEqual(inferred_level({'ram_gb':8,'vram_gb':None}),'weak')
    def test_high_needs_ram_and_vram(self):
        self.assertEqual(inferred_level({'ram_gb':32,'vram_gb':16}),'high')
        self.assertEqual(inferred_level({'ram_gb':16,'vram_gb':16}),'medium')
    def test_missing_models_are_never_selected(self):
        self.assertIsNone(available_choice(['qwen2.5:7b'],[]))
        self.assertEqual(available_choice(['qwen2.5:7b','qwen2.5:3b'],['qwen2.5:3b']),'qwen2.5:3b')
    def test_large_ai_requires_measured_capacity(self):
        self.assertNotIn('qwen2.5-coder:32b',recommendations('high',{'ram_gb':16,'vram_gb':8})['code'])
        self.assertIn('qwen2.5-coder:32b',recommendations('high',{'ram_gb':64,'vram_gb':24})['code'])
    def test_levels_choose_different_context_budgets(self):
        self.assertEqual([recommendations(level)['num_ctx'] for level in ['weak','medium','high']],[2048,8192,8192])
    def test_weak_code_can_use_installed_small_chat_model(self):
        self.assertEqual(available_choice(recommendations('weak')['code'],['qwen2.5:1.5b']),'qwen2.5:1.5b')

if __name__=='__main__':unittest.main()
