import json
import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.document_memory import DocumentMemory
from assistant.online_automation import tutorial_unread

class ManualIdentityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/'test.db');self.memory=DocumentMemory(self.store)
        for file,text in [('PLAXIS_2D_1_Tutorial.pdf','3 Submerged construction of an excavation........52\n4 Stabilisation of a rock slope........72\n[trang 59]\n(10 20)'),
                          ('PLAXIS_3D_1_Tutorial.pdf','3 Loading of a suction pile........59\n4 Stability of a diaphragm wall excavation........71\n[trang 59]\n(99 99)')]:
            self.memory.remember('alice',[{'file':file,'content':text}])
    def test_same_chapter_selects_explicit_product(self):
        for product,title in [('2D','Submerged construction'),('3D','Loading of a suction pile')]:
            result=self.memory.tutorial('alice',[{'role':'user','content':f'PLAXIS {product} chương 3 Case A'}])
            self.assertTrue(result['title'].startswith(title));self.assertEqual(result['product'],product.lower())
            self.assertEqual(result['case'],'A')
    def test_number_alone_cannot_select_between_two_manuals(self):
        self.assertIsNone(self.memory.tutorial('alice',[{'role':'user','content':'chương 3'}]))
    def test_continuation_keeps_user_product_not_assistant_guess(self):
        messages=[{'role':'user','content':'PLAXIS 2D chương 3'},
                  {'role':'assistant','content':'PLAXIS 3D suction pile'},
                  {'role':'user','content':'ok'}]
        self.assertEqual(self.memory.tutorial('alice',messages)['product'],'2d')
    def test_coordinates_do_not_leak_from_other_manual(self):
        info=self.memory.tutorial('alice',[{'role':'user','content':'PLAXIS 2D chương 3'}])
        self.assertNotIn((99.0,99.0),info['coords'])
        context=self.memory.context('alice','PLAXIS 2D chương 3',messages=[{'role':'user','content':'PLAXIS 2D chương 3'}])
        self.assertNotIn('Loading of a suction pile',context)
    def test_wrong_product_commands_are_blocked(self):
        state={'tutorial':{'number':3,'title':'Excavation','product':'2d','page':52,'file':'PLAXIS_2D_1_Tutorial.pdf'},'messages':[]}
        result=tutorial_unread(state,{'version':'3d','commands':[{'command':'soilmat'}]},self.store)
        self.assertIn('Sai manual',result)
    def test_reading_same_page_in_other_file_is_not_evidence(self):
        state={'account_username':'bob','tutorial':{'number':3,'title':'Excavation','product':'2d','page':52,'end':71,'file':'PLAXIS_2D_1_Tutorial.pdf'},
               'messages':[{'role':'tool','tool_name':'pdf_read','content':json.dumps({'ok':True,'path':'PLAXIS_3D_1_Tutorial.pdf','range_start':0,'locations':['trang 59']})}]}
        result=tutorial_unread(state,{'version':'2d','commands':[{'command':'soilmat'}]},self.store)
        self.assertIn('Chưa đọc trang',result)
