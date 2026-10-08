import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from assistant.storage import Store
from assistant.online_automation import OnlineAutomation,planning_messages

class AutomationTopicTests(unittest.TestCase):
    def test_error_question_is_answered_without_planner_or_app_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'state.db');cid=store.create(False)
            client=Mock();tools=Mock()
            agent=OnlineAutomation(client,{'windows_apps_enabled':True},store,cid,tools,tools,plaxis_remote=tools)
            for error in ('auto_run phải là chuỗi','Expecting value: line 1 column 1 (char 0)'):
                state={'messages':[{'role':'assistant','content':'AI chưa trả kế hoạch hợp lệ. '+error}]}
                agent.start(state,'Bạn đang bị lỗi gì thế','DeepSeek Flash','alice')
                events=list(agent.run(state))
                self.assertIn('chưa thực hiện thao tác',events[0]['text'])
                self.assertFalse(state['running']);self.assertEqual(state['queue'],[])
            self.assertFalse(client.mock_calls);self.assertFalse(tools.mock_calls)
    def test_greeting_after_plaxis_does_not_plan_or_replay_results(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'state.db');cid=store.create(False)
            client=Mock();tools=Mock()
            agent=OnlineAutomation(client,{'windows_apps_enabled':True},store,cid,tools,tools,plaxis_remote=tools)
            state={'messages':[{'role':'user','content':'Chạy PLAXIS'},
                               {'role':'tool','tool_name':'plaxis_run_problem','content':'Lún: 344894.17 mm'},
                               {'role':'assistant','content':'Đã có kết quả.'}]}
            agent.start(state,'hi','DeepSeek Flash','alice')
            events=list(agent.run(state))
            self.assertIn('Chào bạn',events[0]['text'])
            self.assertNotIn('PLAXIS',state['messages'][-1]['content'])
            self.assertFalse(state['running']);self.assertEqual(state['queue'],[])
            self.assertFalse(client.mock_calls);self.assertFalse(tools.mock_calls)
    def test_previous_tool_is_labelled_history_and_current_tool_stays_current(self):
        state={'messages':[{'role':'tool','tool_name':'plaxis_run_problem','content':'old'},
                           {'role':'user','content':'Hỏi câu mới'},
                           {'role':'tool','tool_name':'browser_search','content':'new'}]}
        messages=planning_messages(state,'instruction')
        self.assertEqual(messages[1]['role'],'assistant')
        self.assertIn('LỊCH SỬ',messages[1]['content'])
        self.assertIn('LƯỢT HIỆN TẠI',messages[3]['content'])
