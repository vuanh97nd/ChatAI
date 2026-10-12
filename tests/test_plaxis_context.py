import copy
import json
import unittest

from assistant.plaxis_context import compact_schemas, planning_messages, planning_instruction


class PlaxisContextTests(unittest.TestCase):
    def test_all_required_parameters_and_enums_stay_exact(self):
        schema=[{'function':{'name':'plaxis_commands','description':'X'*30000,
            'parameters':{'type':'object','required':['version','target','commands'],
            'properties':{'version':{'enum':['2d','3d']},'target':{'enum':['input','output']},
                          'commands':{'type':'array'}}}}}]
        original=copy.deepcopy(schema)
        compact=compact_schemas(schema)
        self.assertEqual(compact[0]['function']['parameters'],schema[0]['function']['parameters'])
        self.assertEqual(schema,original)
        self.assertLess(len(json.dumps(compact)),len(json.dumps(schema))/10)

    def test_long_run_bounded_without_losing_latest_error_or_current_constraints(self):
        state={'messages':[{'role':'user','content':'Bài 4, polygon, không xét nước.'}]}
        for i in range(300):
            state['messages'].extend([
                {'role':'assistant','tool_calls':[{'function':{'name':'plaxis_commands','arguments':'BAD_OLD_JSON'}}]},
                {'role':'tool','tool_name':'plaxis_commands','content':'result-'+str(i)+' x'*1000}])
        state['messages'].extend([{'role':'user','content':'Giữ nguyên tường, tiếp tục Phase_4.'},
            {'role':'tool','tool_name':'plaxis_commands','content':json.dumps({'ok':False,
                'error':'Thiếu version','readback':{'Active':None,'phase':'Phase_4','region':{'x':[40,60],'y':[20,23]}}})}])
        before=copy.deepcopy(state)
        result=planning_messages(state,'Instructions')
        text=json.dumps(result,ensure_ascii=False)
        self.assertLess(len(text),21000)
        for value in ('Bài 4','không xét nước','Giữ nguyên tường','Thiếu version','null','Phase_4'):
            self.assertIn(value,text)
        self.assertNotIn('BAD_OLD_JSON',text)
        self.assertEqual(state,before)

    def test_large_observation_is_explicitly_incomplete_and_preserves_error_tail(self):
        state={'messages':[{'role':'user','content':'Inspect'},
            {'role':'tool','tool_name':'plaxis_commands','content':'x'*20000+'FINAL_ERROR_INVALID_ACTIVE'}]}
        text=json.dumps(planning_messages(state,'Instructions'),ensure_ascii=False)
        self.assertIn('KHÔNG đầy đủ',text)
        self.assertIn('FINAL_ERROR_INVALID_ACTIVE',text)

    def test_current_user_and_latest_screenshot_retained(self):
        state={'messages':[{'role':'user','content':'a'*22000,'images':['user-image']},
            {'role':'tool','tool_name':'windows_screenshot','content':'screenshot','images':['tool-image']}]}
        result=planning_messages(state,'Instructions',lambda text,image:[text,image])
        text=json.dumps(result)
        self.assertIn('a'*22000,text)
        self.assertIn('user-image',text)
        self.assertIn('tool-image',text)

    def test_prompt_retains_permissions_and_verification(self):
        text=planning_instruction([],'SCOPE_ONLY_REGISTERED_APPS',True)
        for token in ('SCOPE_ONLY_REGISTERED_APPS','verify_model','CalculationResult','version',
                      'Active=None','phase','không hỏi xác nhận bắt đầu'):
            self.assertIn(token,text)
