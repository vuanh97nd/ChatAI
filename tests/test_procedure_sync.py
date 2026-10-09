import copy
import json
import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.procedure_memory import ProcedureMemory
from assistant.procedure_sync import ProcedureSync


class Backend:
    def __init__(self):self.rows={};self.seq=0;self.fail=False
    def __call__(self,path,body):
        if self.fail:raise RuntimeError('offline')
        owner='@shared' if body.get('scope')=='shared' else body['username']
        if path.endswith('/put'):
            if owner=='@shared' and body['username']!='admin':raise RuntimeError('forbidden')
            for record in body['records']:
                self.seq+=1;self.rows[(owner,record['id'])]={'scope':'shared' if owner=='@shared' else 'private','owner':owner,'record':copy.deepcopy(record),'seq':self.seq}
            return {'success':True}
        if path.endswith('/list'):
            rows=sorted((r for r in self.rows.values() if r['owner'] in (body['username'],'@shared') and r['seq']>body['cursor']),key=lambda r:r['seq'])[:50]
            return {'items':copy.deepcopy(rows),'cursor':rows[-1]['seq'] if rows else body['cursor'],'has_more':len(rows)==50}
        raise AssertionError(path)


class ProcedureSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'a.db');self.memory=ProcedureMemory(self.store);self.backend=Backend()
        self.session={'username':'alice','key':'fixture','endpoint':'https://example.org'}

    def teach(self,owner,count,training=False):
        for i in range(count):
            self.memory.remember(owner,{'messages':[{'role':'user','content':'PLAXIS dựng mô hình riêng tại C:\\private\\a.p2dx'}]},
                {'function':{'name':'plaxis_commands','arguments':{'index':i,'path':'C:\\private\\a.p2dx'}}},
                {'ok':True},training=training)

    def test_more_than_snapshot_limit_survives_other_device_and_restart(self):
        self.teach('alice',135)
        self.assertEqual(len(self.memory.records('alice')),135)
        self.assertEqual(len(self.memory.export('alice')),20)
        sync=ProcedureSync(self.store,self.session,self.backend);sync.cycle()
        other=Store(Path(self.tmp.name)/'b.db');ProcedureSync(other,self.session,self.backend).cycle()
        self.assertEqual(len(ProcedureMemory(other).records('alice')),135)
        before=self.backend.seq;sync.cycle();self.assertEqual(self.backend.seq,before)

    def test_only_admin_training_is_shared_and_private_tasks_are_scrubbed(self):
        self.teach('admin',1,True);self.teach('alice',1,True)
        ProcedureSync(self.store,dict(self.session,username='admin'),self.backend).cycle()
        ProcedureSync(self.store,self.session,self.backend).cycle()
        shared=[r for (owner,_),r in self.backend.rows.items() if owner=='@shared']
        self.assertEqual(len(shared),1)
        self.assertNotIn('private',json.dumps(shared[0]['record']))
        other=Store(Path(self.tmp.name)/'b.db');ProcedureSync(other,dict(self.session,username='bob'),self.backend).cycle()
        memory=ProcedureMemory(other)
        self.assertIn('Đào tạo',memory.context('bob','PLAXIS'))
        self.assertEqual(memory.records('alice'),[])

    def test_offline_keeps_all_pending_records_for_retry(self):
        self.teach('alice',35);self.backend.fail=True
        with self.assertRaises(RuntimeError):ProcedureSync(self.store,self.session,self.backend).cycle()
        self.assertEqual(len(self.memory.records('alice')),35)
        self.backend.fail=False;ProcedureSync(self.store,self.session,self.backend).cycle()
        self.assertEqual(len(self.backend.rows),35)

    def test_shared_withdrawal_is_applied_without_executing(self):
        self.teach('admin',1,True)
        ProcedureSync(self.store,dict(self.session,username='admin'),self.backend).cycle()
        sync=ProcedureSync(self.store,self.session,self.backend);sync.cycle()
        self.assertTrue(self.memory.context('alice','PLAXIS'))
        shared=next(r for r in self.backend.rows.values() if r['owner']=='@shared')
        self.backend.seq+=1;shared.update(deleted=True,seq=self.backend.seq)
        sync.cycle();self.assertEqual(self.memory.context('alice','PLAXIS'),'')
