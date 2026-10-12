import copy
import base64
import json
import unittest
from assistant.online_automation import planning_messages
from assistant.nvidia_planning import schemas_for_nvidia


class NvidiaPlanningTests(unittest.TestCase):
    def state(self):
        messages=[{'role':'user','content':'Dựng bài PLAXIS; đất y=15 tới -13, đào tới y=6 rồi y=0.'}]
        for i in range(80):
            messages.extend([
                {'role':'assistant','content':'','tool_calls':[{'function':{'name':'plaxis_commands','arguments':{'commands':'BROKEN_OLD_ARGUMENTS'}}}]},
                {'role':'tool','tool_name':'plaxis_commands','content':json.dumps({'ok':True,'readback':('readback-'+str(i)+' ')*1400})}])
        messages.append({'role':'user','content':'Tiếp tục, giữ đất ngoài vùng đào.'})
        messages.append({'role':'tool','tool_name':'plaxis_commands','content':'{"ok":false,"error":"gammaSat read-only","phase_hint":"gotostages"}'})
        return {'messages':messages}

    def test_deepseek_context_remains_exactly_legacy(self):
        state=self.state();before=copy.deepcopy(state)
        expected=planning_messages(state,'Instructions')
        for provider in ('deepseek_flash','deepseek','deepseek_r1',''):
            self.assertEqual(planning_messages(state,'Instructions',provider),expected)
        self.assertEqual(state,before)

    def test_nvidia_context_is_smaller_keeps_current_request_and_latest_failure(self):
        state=self.state();before=copy.deepcopy(state)
        legacy=json.dumps(planning_messages(state,'Instructions'),ensure_ascii=False)
        compact=planning_messages(state,'Instructions','nvidia')
        text=json.dumps(compact,ensure_ascii=False)
        self.assertLess(len(text),len(legacy)/3)
        self.assertIn('giữ đất ngoài vùng đào',text)
        self.assertIn('gammaSat read-only',text)
        self.assertIn('gotostages',text)
        self.assertNotIn('BROKEN_OLD_ARGUMENTS',text)
        self.assertEqual(state,before)

    def test_parameter_schemas_unchanged_and_original_not_mutated(self):
        schemas=[{'function':{'name':'test','description':'X'*6000,'parameters':{'type':'object','required':['path'],'properties':{'path':{'type':'string'}},'additionalProperties':False}}}]
        original=copy.deepcopy(schemas)
        result=schemas_for_nvidia(schemas)
        self.assertEqual(result[0]['function']['parameters'],schemas[0]['function']['parameters'])
        self.assertLess(len(result[0]['function']['description']),1500)
        self.assertEqual(schemas,original)

    def test_latest_request_survives_more_than_twelve_tool_results(self):
        state={'messages':[{'role':'user','content':'Không xóa tường, chỉ đọc Phase_3.'}]+
               [{'role':'tool','tool_name':'plaxis_commands','content':'read-'+str(i)} for i in range(50)]}
        text=json.dumps(planning_messages(state,'Instructions','nvidia'),ensure_ascii=False)
        self.assertIn('Không xóa tường',text)
        self.assertIn('read-49',text)

    def test_latest_tool_screenshot_is_kept_for_visual_actions(self):
        encoded=base64.b64encode(b'\xff\xd8\xff'+b'\x00'*6).decode()
        state={'messages':[{'role':'user','content':'Đọc cửa sổ này'},
                           {'role':'tool','tool_name':'windows_screenshot','content':'Screenshot received','images':[encoded]}]}
        messages=planning_messages(state,'Instructions','nvidia')
        images=[m for m in messages if isinstance(m['content'],list)]
        self.assertEqual(len(images),1)
        self.assertIn(encoded,json.dumps(images))


if __name__=='__main__':unittest.main()
