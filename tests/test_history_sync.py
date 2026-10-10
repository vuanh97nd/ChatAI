import copy
import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.history_sync import HistorySync,dialogue


class Backend:
    def __init__(self):self.rows={};self.fail=False
    def __call__(self,path,body):
        if self.fail:raise RuntimeError('offline')
        owner=body['username'];cid=body.get('conversation_id');action=path.rsplit('/',1)[1]
        key=(owner,cid)
        if action=='list':return {'items':[{'id':c,'revision':r['revision'],'deleted':r['deleted']} for (u,c),r in self.rows.items() if u==owner],'next_offset':None}
        if action=='get':return copy.deepcopy(self.rows[key])
        if action=='put':
            revision=self.rows.get(key,{}).get('revision',0)
            if revision!=body['revision']:raise RuntimeError('conflict')
            self.rows[key]={'state':copy.deepcopy(body['state']),'revision':revision+1,'deleted':body['deleted']}
            return {'revision':revision+1}
        raise AssertionError(path)


class HistorySyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Store(Path(self.tmp.name)/'a.db');self.b=Store(Path(self.tmp.name)/'b.db');self.backend=Backend()
        self.session={'username':'alice','key':'test','endpoint':'https://example.org'}
        self.sa=HistorySync(self.a,self.session,self.backend);self.sb=HistorySync(self.b,self.session,self.backend)
    def conversation(self,store,text='Dùng mét, cọc D=0,8 m.'):
        cid=store.create(False);store.save(cid,{'messages':[{'role':'user','content':text},{'role':'assistant','content':'Đã ghi nhận.'}], 'account_username':'alice','queue':[],'pending':None,'running':False,'model':'DeepSeek Flash'})
        return cid
    def test_upload_restart_and_other_device_restore(self):
        cid=self.conversation(self.a);self.sa.cycle();self.assertTrue(self.sb.cycle())
        self.assertEqual(dialogue(self.a.load(cid)),dialogue(self.b.load(cid)))
        # Repeat after restart is idempotent.
        HistorySync(Store(self.a.path),self.session,self.backend).cycle()
        self.assertEqual(self.backend.rows[('alice',cid)]['revision'],1)
    def test_offline_retains_history_and_retries(self):
        cid=self.conversation(self.a);self.backend.fail=True
        with self.assertRaises(RuntimeError):self.sa.cycle()
        self.assertTrue(self.a.load(cid)['messages']);self.backend.fail=False;self.sa.cycle()
        self.assertIn(('alice',cid),self.backend.rows)
    def test_account_isolation(self):
        cid=self.conversation(self.a);self.sa.cycle()
        HistorySync(self.b,dict(self.session,username='bob'),self.backend).cycle()
        self.assertEqual(self.b.list(),[])
    def test_concurrent_edits_preserve_both(self):
        cid=self.conversation(self.a);self.sa.cycle();self.sb.cycle()
        for store,text in [(self.a,'Bản A'),(self.b,'Bản B')]:
            s=store.load(cid);s['messages'].append({'role':'user','content':text});store.save(cid,s)
        self.sa.cycle();self.sb.cycle();self.sb.cycle()
        texts=[self.b.load(c)['messages'][-1]['content'] for c,_ in self.b.list()]
        self.assertCountEqual(texts,['Bản A','Bản B'])
    def test_delete_and_undo_do_not_resurrect_from_cloud(self):
        cid=self.conversation(self.a);self.sa.cycle();self.sb.cycle()
        backup=self.a.delete(cid,Path(self.tmp.name)/'backup');self.sa.cycle();self.sb.cycle()
        self.assertEqual(self.b.list(),[])
        self.a.restore_deleted(backup,'alice');self.sa.cycle();self.sb.cycle()
        self.assertTrue(self.b.load(cid)['messages'])
    def test_active_actions_are_not_uploaded_or_resumed(self):
        cid=self.conversation(self.a);s=self.a.load(cid);s['running']=True;s['queue']=[{'tool':'danger'}];self.a.save(cid,s)
        # A running/queued conversation may back up its dialogue, but never the queue or running flag.
        self.sa.cycle();self.assertNotIn('danger',str(self.backend.rows));self.assertNotIn("'running': True",str(self.backend.rows))
        s['running']=False;s['queue']=[];s['api_key']='secret';s['messages'][0]['images']=['private-image'];self.a.save(cid,s)
        self.sa.cycle();self.sb.cycle()
        raw=str(self.backend.rows);self.assertNotIn('secret',raw);self.assertNotIn('private-image',raw)
        self.assertFalse(self.b.load(cid)['running']);self.assertEqual(self.b.load(cid)['queue'],[])
    def test_tool_history_restored_for_planner(self):
        from assistant.online_automation import planning_messages
        cid=self.conversation(self.a);s=self.a.load(cid);s['messages'].append({'role':'tool','content':'đã tạo','tool_name':'word_create_open'});self.a.save(cid,s)
        self.sa.cycle();self.sb.cycle()
        self.assertIn('word_create_open',planning_messages(self.b.load(cid),'test')[-1]['content'])
