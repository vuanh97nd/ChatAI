import json
import unittest
from unittest.mock import patch

from assistant.turn_intent import validate_research_plan,is_web_research
from assistant.online_automation import search_call,planning_messages
from assistant.plaxis_commands import commands_from_json

URL='https://bentleysystems.service-now.com/community?id=kb_article&sysparm_article=KB0107775'
REQUEST='Tìm kiếm trang này '+URL+' đọc các tài liệu về API/python dùng trong Plaxis'


class TurnIntentTests(unittest.TestCase):
    def test_online_turn_reads_web_without_resuming_old_model(self):
        from tests.test_online_automation import OnlineAutomationTest
        fixture=OnlineAutomationTest()
        fixture.setUp()
        try:
            fixture.state['messages']=[
                {'role':'user','content':'Làm bài 7 PLAXIS'},
                {'role':'tool','tool_name':'plaxis_run_problem','content':'{"ok":false,"error":"plxscripting missing"}'},
                {'role':'assistant','content':'Đã tạo tường, còn thiếu neo.'}]
            fixture.state['tutorial']={'number':7,'title':'Dry excavation using a tie back wall',
                                      'page':100,'file':'manual.pdf','product':'2d'}
            fixture.agent.plaxis_app=object()
            fixture.responses=[json.dumps({'answer':'Nguồn web đã đọc có thông tin API.', 'tool':'','arguments':{}})]
            with patch('assistant.installed_apps.authorized_apps',return_value=[{'path':r'C:\Apps\chrome.exe'}]):
                fixture.agent.start(fixture.state,REQUEST,'DeepSeek API','admin')
            self.assertEqual(fixture.state['queue'][0]['function']['name'],'browser_run')
            list(fixture.agent.run(fixture.state))
            self.assertEqual(fixture.state['pending']['plan']['action'],'browser_run')
            fixture.agent.approve(fixture.state,True,fixture.state['pending'])
            list(fixture.agent.run(fixture.state))
            self.assertEqual([p['action'] for p in fixture.committed],['browser_run'])
            self.assertFalse(any('BÀI ĐANG LÀM:' in str(m.get('content')) for m in fixture.requests[0]))
            self.assertEqual(fixture.state['messages'][-1]['content'],'Nguồn web đã đọc có thông tin API.')
        finally:
            fixture.tearDown()

    def test_exact_user_request_opens_supplied_url_without_chrome_keyword(self):
        with patch('assistant.installed_apps.authorized_apps',return_value=[{'path':r'C:\Apps\chrome.exe'}]):
            call=search_call(REQUEST,{'windows_apps_enabled':True})
        self.assertEqual(call['function']['name'],'browser_run')
        self.assertEqual(json.loads(call['function']['arguments']['steps']),
                         [{'action':'navigate','url':URL},{'action':'read'}])

    def test_old_success_cannot_substitute_for_current_lookup(self):
        state={'messages':[{'role':'tool','tool_name':'browser_run','content':'{"ok":true}'},
                           {'role':'user','content':REQUEST}]}
        with self.assertRaisesRegex(ValueError,'Chưa đọc web'):
            validate_research_plan({'tool':'','answer':'Đã thiết lập mô hình'},state)
        with self.assertRaisesRegex(ValueError,'không sửa mô hình'):
            validate_research_plan({'tool':'plaxis_commands'},state)
        validate_research_plan({'tool':'browser_run'},state)

    def test_failed_lookup_is_reportable_without_inventing_page_contents(self):
        state={'messages':[{'role':'user','content':REQUEST},
                           {'role':'tool','tool_name':'browser_run','content':'{"ok":false,"error":"Login required"}'}]}
        validate_research_plan({'tool':'','answer':'Chưa đọc được: cần đăng nhập.'},state)

    def test_even_after_lookup_repeated_old_report_is_rejected(self):
        old='Đã thiết lập dự án PLAXIS, tạo địa tầng, vật liệu, tường và neo. '*5
        state={'messages':[{'role':'assistant','content':old},{'role':'user','content':REQUEST},
                           {'role':'tool','tool_name':'browser_run','content':'{"ok":true}'}]}
        with self.assertRaisesRegex(ValueError,'lặp câu trả lời lịch sử'):
            validate_research_plan({'tool':'','answer':old},state)

    def test_model_work_and_short_followups_are_not_research(self):
        for text in ('tiếp tục','Dựng bài 7 PLAXIS','Tính mô hình theo manual','Không cần đọc lại '+URL):
            self.assertFalse(is_web_research(text))
            validate_research_plan({'tool':'plaxis_commands'},{'messages':[{'role':'user','content':text}]})

    def test_latest_request_is_explicit_after_old_tool_history(self):
        state={'messages':[{'role':'user','content':'Làm bài 7'},
                           {'role':'tool','tool_name':'plaxis_commands','content':'{"ok":true}'},
                           {'role':'assistant','content':'Đã tạo tường'},
                           {'role':'user','content':REQUEST}]}
        messages=planning_messages(state,'Tools')
        self.assertIn(REQUEST,messages[0]['content'])
        self.assertIn('LỊCH SỬ',messages[2]['content'])

    def test_wrapper_lookup_is_rejected_with_correct_call_guidance(self):
        for helper in ('inspect_stage','verify_stage','inspect_progress','plan_resume'):
            with self.assertRaisesRegex(ValueError,'wrapper Chat AI'):
                commands_from_json(json.dumps([{'command':'info','args':[{'ref':'g.'+helper}]}]))
            with self.assertRaisesRegex(ValueError,'wrapper Chat AI'):
                commands_from_json(json.dumps([{'command':'signature','args':['g.'+helper]}]))
        commands_from_json(json.dumps([{'command':'inspect_stage','args':[{'ref':'g.Phase_1'},{'ref':'g.Soils'}]}]))
