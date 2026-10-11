import unittest
from assistant.communication import MethodRequired,require_method,validate_methods,method_status

class CommunicationTests(unittest.TestCase):
    def test_com_requires_user_enablement_even_with_task_autonomy(self):
        cfg={'ai_tools_auto_execute':True,'communication_methods':{'com':False}};validate_methods(cfg)
        with self.assertRaisesRegex(MethodRequired,'Cần bật phương thức COM'):
            require_method(cfg,'excel_com')
        cfg['communication_methods']['com']=True
        require_method(cfg,'excel_com')
        cfg['communication_methods']['com']=False
        with self.assertRaises(MethodRequired):require_method(cfg,'excel_com')
    def test_methods_can_be_disabled_independently(self):
        cfg={'communication_methods':{'screen':False,'application_api':False,'files':False}}
        for name in ('windows_capture','plaxis_commands','excel_read'):
            with self.assertRaisesRegex(MethodRequired,'Cài đặt → Phương thức kết nối'):require_method(cfg,name)
        require_method(cfg,'windows_input')
        require_method(cfg,'calculate')
    def test_invalid_settings_rejected(self):
        for value in ('all',{'com':'yes'},{'unknown':True}):
            with self.assertRaises(ValueError):validate_methods({'communication_methods':value})
    def test_status_distinguishes_disabled_from_unimplemented(self):
        text=method_status({})
        self.assertIn('Plugin / Add-in',text)
        self.assertIn('application_connections',text)
        self.assertIn('không tự bật',text)
    def test_com_defaults_on_and_other_new_methods_can_be_enabled(self):
        cfg={};validate_methods(cfg)
        self.assertTrue(cfg['communication_methods']['com'])
        for method,tool in [('plugin','plugin_call'),('macro','vba_execute'),('http','application_websocket'),('ipc','application_ipc')]:
            with self.assertRaises(MethodRequired):require_method(cfg,tool)
            cfg['communication_methods'][method]=True
            require_method(cfg,tool)

    def test_uncertain_connection_result_stops_replay_but_not_success(self):
        from assistant.communication import connection_failure_answer
        self.assertIn('Kiểm tra dữ liệu',connection_failure_answer('application_ipc',{'ok':False,'uncertain':True,'error':'timeout'}))
        self.assertEqual(connection_failure_answer('vba_execute',{'method_required':True,'error':'Cần bật VBA'}),'Cần bật VBA')
        self.assertIsNone(connection_failure_answer('vba_execute',{'ok':True}))
        self.assertIsNone(connection_failure_answer('calculate',{'uncertain':True}))
    def test_planner_normalizes_structured_connection_payload(self):
        import json
        from assistant.online_automation import parse_plan
        from assistant.tools import EXTRA_TOOLS
        SCHEMAS=[spec for module,spec in EXTRA_TOOLS if module=='application_transport']
        output=parse_plan(json.dumps({'tool':'plugin_call','arguments':{'connection':'office','function':'sum','payload':[1,2]},'answer':''}),SCHEMAS)
        self.assertEqual(json.loads(output['arguments']['payload']),[1,2])
