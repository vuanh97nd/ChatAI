import json
import unittest
from types import SimpleNamespace
from assistant.routing import classify_question, CATEGORIES
from assistant.prompts import SYSTEM_PROMPT, SYSTEM, FAST_SYSTEM
import test_app as fixtures


class RouterClient:
    def __init__(self, value=None, error=None):
        self.value, self.error, self.calls = value, error, []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(message=SimpleNamespace(content=self.value))


def payload(category, **flags):
    return json.dumps(dict(category=category, creative=flags.get('creative', False),
        complex=flags.get('complex', False), high_accuracy=flags.get('high_accuracy', False)))


class RoutingTest(unittest.TestCase):
    def route(self, client, text='Giải thích định luật Newton', documents=False):
        return classify_question(client, [{'role': 'user', 'content': text}], documents)

    def test_prompt_length_including_mode_rules(self):
        for prompt in (SYSTEM_PROMPT, SYSTEM, FAST_SYSTEM):
            self.assertLess(len(prompt.split()), 700)

    def test_categories_and_temperature(self):
        for category in CATEGORIES:
            with self.subTest(category=category):
                client = RouterClient(payload(category))
                route = self.route(client)
                self.assertEqual(route['category'], category)
                self.assertEqual(route['temperature'], .5 if category == 'conversation' else
                    (.3 if category == 'writing_translation' else .2))
                self.assertFalse(route['review_recommended'])
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(client.calls[0]['model'], 'qwen2.5:7b')
                self.assertFalse(client.calls[0]['stream'])
                self.assertIn('format', client.calls[0])

    def test_classifier_uses_selected_model(self):
        for model in ('qwen2.5:3b','deepseek-r1:8b'):
            client=RouterClient(payload('knowledge'))
            classify_question(client,[{'role':'user','content':'Giải thích lực hấp dẫn'}],model=model)
            self.assertEqual(client.calls[0]['model'],model)

    def test_translation_differs_from_creative_writing(self):
        self.assertEqual(self.route(RouterClient(payload('writing_translation', creative=True)))['temperature'], .75)
        self.assertEqual(self.route(RouterClient(payload('writing_translation')))['temperature'], .3)

    def test_invalid_json_bad_flags_and_backend_errors_fallback(self):
        clients = [RouterClient('not json'), RouterClient('[]'),
            RouterClient(payload('unknown')), RouterClient('{"category":"coding","creative":"false"}'),
            RouterClient(error=TimeoutError('offline'))]
        for client in clients:
            with self.subTest(client=client):
                route = self.route(client, 'Viết code Python tính tổng')
                self.assertEqual(route['category'], 'coding')
                self.assertEqual(route['source'], 'fallback')
                self.assertEqual(route['temperature'], .2)

    def test_attachment_overrides_greeting_and_model_guess(self):
        client = RouterClient(payload('conversation'))
        route = self.route(client, 'Xin chào', True)
        self.assertEqual(route['category'], 'personal_documents')
        self.assertEqual(len(client.calls), 1)

    def test_greeting_fast_path_without_model(self):
        client = RouterClient(error=RuntimeError('must not call'))
        self.assertEqual(self.route(client, 'Xin chào!')['source'], 'fast_path')
        self.assertEqual(client.calls, [])

    def test_review_metadata_for_hard_and_high_stakes_only(self):
        self.assertTrue(self.route(RouterClient(payload('knowledge', complex=True)))['review_recommended'])
        self.assertTrue(self.route(RouterClient(payload('knowledge', high_accuracy=True)))['review_recommended'])
        self.assertFalse(self.route(RouterClient(payload('conversation')))['review_recommended'])

    def test_images_not_sent_to_classifier(self):
        client = RouterClient(payload('knowledge'))
        classify_question(client, [{'role': 'user', 'content': 'Ảnh này là gì?', 'images': ['private_base64']}])
        self.assertNotIn('private_base64', json.dumps(client.calls))


class PipelineTest(unittest.TestCase):
    setUp = fixtures.AppTest.setUp
    tearDown = fixtures.AppTest.tearDown
    def test_temperature_applied_once_and_new_turn_resets_route(self):
        class Client(fixtures.FakeClient):
            def __init__(self):
                super().__init__([[fixtures.chunk('Bản sáng tác')], [fixtures.chunk('Bản dịch')]])
                self.routes = iter(['writing_translation', 'writing_translation'])
                self.classifications = 0

            def chat(self, **kwargs):
                if kwargs.get('stream') is False:
                    self.classifications += 1
                    return {'message': {'content': payload(next(self.routes), creative=self.classifications == 1)}}
                return super().chat(**kwargs)
        from assistant.agent import Agent
        client = Client()
        agent = Agent(client, self.excel, self.cfg, self.store, self.cid, tools_enabled=False)
        state = self.store.load(self.cid)
        agent.start(state, 'Sáng tác một bài thơ', 'qwen2.5:7b')
        events = list(agent.run(state))
        self.assertTrue(any(e['type'] == 'status' for e in events))
        self.assertEqual(client.requests[0]['options']['temperature'], .75)
        self.assertEqual(self.store.load(self.cid)['routing']['category'], 'writing_translation')
        agent.start(state, 'Dịch câu này sang tiếng Việt', 'qwen2.5:7b')
        list(agent.run(state))
        self.assertEqual(client.requests[1]['options']['temperature'], .3)
        self.assertEqual(client.classifications, 2)
        self.assertFalse(state['running'])


if __name__ == '__main__':
    unittest.main()
