import unittest
from types import SimpleNamespace

from assistant.automation_start import start_automation


class AutomationStartTests(unittest.TestCase):
    def test_text_turn_works_with_legacy_module(self):
        calls = []
        agent = SimpleNamespace(start=lambda state, prompt, model, owner:
                                calls.append((state, prompt, model, owner)))
        start_automation(agent, {}, 'Bạn cần quyền gì?', 'DeepSeek Flash', 'admin')
        self.assertEqual(calls, [({}, 'Bạn cần quyền gì?', 'DeepSeek Flash', 'admin')])

    def test_image_turn_keeps_image_with_current_module(self):
        calls = []
        agent = SimpleNamespace(start=lambda state, prompt, model, owner, image=None:
                                calls.append(image))
        start_automation(agent, {}, 'Đọc ảnh', 'DeepSeek Flash', 'admin', image='encoded')
        self.assertEqual(calls, ['encoded'])

    def test_legacy_image_turn_fails_before_any_action(self):
        calls = []
        agent = SimpleNamespace(start=lambda state, prompt, model, owner: calls.append(prompt))
        with self.assertRaisesRegex(RuntimeError, 'cập nhật toàn bộ ChatAI'):
            start_automation(agent, {}, 'Đọc ảnh', 'DeepSeek Flash', 'admin', image='encoded')
        self.assertEqual(calls, [])

    def test_internal_type_error_is_not_retried(self):
        calls = []
        def start(state, prompt, model, owner, image=None):
            calls.append(prompt)
            raise TypeError('internal failure')
        with self.assertRaisesRegex(TypeError, 'internal failure'):
            start_automation(SimpleNamespace(start=start), {}, 'Đọc ảnh', 'DeepSeek Flash', 'admin', image='encoded')
        self.assertEqual(calls, ['Đọc ảnh'])
