import unittest
from assistant.node_tool_bridge import planning_contract, unsupported_denial
from assistant.online_automation import use_automation, check_confirmation


class NodeToolBridgeTests(unittest.TestCase):
    def test_contract_uses_only_actual_tools(self):
        text, names=planning_contract([{'function':{'name':'plaxis_commands'}}])
        self.assertEqual(names,['plaxis_commands'])
        self.assertIn('external Windows application',text)
        self.assertNotIn('geostudio_python',text)

    def test_real_connection_error_is_not_tool_denial(self):
        self.assertIsNone(unsupported_denial('Không kết nối được PLAXIS tại cổng 10000.', ['plaxis_commands']))
        self.assertIsNone(unsupported_denial('Không có công cụ PLAXIS.', []))
        self.assertEqual(unsupported_denial('Không có công cụ PLAXIS trong phiên này.', ['plaxis_commands']),'plaxis_commands')

    def test_node_planner_cannot_deny_provided_tool(self):
        state={'messages':[], 'node_tool_executor':True,'planning_tool_names':['plaxis_commands']}
        with self.assertRaisesRegex(ValueError,'tool thật plaxis_commands'):
            check_confirmation({'tool':'','arguments':{},'answer':'Không có công cụ PLAXIS.'},state,{})

    def test_continuation_routes_to_tools_without_prior_tool_result(self):
        state={'messages':[{'role':'user','content':'Làm bài TBM trong PLAXIS 3D.'}]}
        self.assertTrue(use_automation('tiếp tục',{'windows_apps_enabled':True},state))
        self.assertFalse(use_automation('tiếp tục',{'windows_apps_enabled':False},state))
        self.assertFalse(use_automation('thời tiết hôm nay',{'windows_apps_enabled':True},state))

if __name__=='__main__': unittest.main()
