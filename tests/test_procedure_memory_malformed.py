import copy
import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.procedure_memory import ProcedureMemory


class MalformedProcedureMemoryTests(unittest.TestCase):
    def test_failed_preparation_with_non_list_args_keeps_original_error(self):
        for malformed in ({'ref':'g.Project'}, 'bad', 1, None):
            with self.subTest(args=malformed), tempfile.TemporaryDirectory() as folder:
                memory=ProcedureMemory(Store(Path(folder)/'history.db'))
                state={'messages':[{'role':'user','content':'Bài 4 PLAXIS'}]}
                call={'function':{'name':'plaxis_commands','arguments':{'version':'2d','target':'input',
                    'commands':[{'command':'read','args':malformed}]}}}
                original=copy.deepcopy(call)
                memory.remember('admin',state,call,{'ok':False,'preparation_failed':True,
                    'not_executed':True,'error':'args phải là mảng'})
                self.assertEqual(call,original)
                self.assertTrue(state['procedure_progress']['steps'])
                records=memory.export('admin')
                self.assertTrue(records)
                self.assertTrue(all(r['outcome']=='failed' for r in records))

