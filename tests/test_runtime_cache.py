import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from assistant.runtime_cache import RuntimeCache,account_scope
from assistant.workflow_memory import WorkflowMemory
from assistant.files import FileTools
from assistant.excel import ExcelTools
from assistant.office import OfficeTools
from assistant.online_office import OnlineOffice
from assistant.windows_apps import resume_automation


class CacheTests(unittest.TestCase):
    def setUp(self):
        resume_automation()
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.clock=[100.0]
        self.cache=RuntimeCache(self.root/'cache.sqlite3',clock=lambda:self.clock[0])
        self.scope=account_scope('owner','https://server')
        self.files=FileTools([self.root],self.root/'backups',lambda *a:None)
    def office(self,scope=None):
        return OnlineOffice(ExcelTools([self.root],self.root/'backups',lambda *a:None),OfficeTools(self.files),self.files,cache=self.cache,cache_scope=scope or self.scope)
    def test_persists_across_instances_expires_and_separates_accounts_servers(self):
        self.cache.put(self.scope,'read','x',{'data':7},ttl=10)
        other=RuntimeCache(self.cache.path,clock=lambda:self.clock[0])
        self.assertEqual(other.get(self.scope,'read','x'),{'data':7})
        self.assertIsNone(other.get(account_scope('other','https://server'),'read','x'))
        self.assertIsNone(other.get(account_scope('owner','https://other'),'read','x'))
        self.clock[0]=110
        self.assertIsNone(other.get(self.scope,'read','x'))
    def test_lru_and_byte_limits(self):
        small=RuntimeCache(self.root/'small.sqlite3',clock=lambda:self.clock[0],max_entries=2,max_bytes=100)
        for key in ('a','b'):small.put('s','k',key,1)
        self.clock[0]+=1;small.get('s','k','a');self.clock[0]+=1;small.put('s','k','c',1)
        self.assertIsNone(small.get('s','k','b'))
        self.assertEqual(small.get('s','k','a'),1)
        self.assertFalse(small.put('s','k','big','x'*110))
    def test_document_parse_reused_for_different_chunks_and_changed_file_invalidates(self):
        p=self.root/'manual.txt';p.write_text('abcdefgh')
        office=self.office()
        with patch('assistant.document_reader.read_bytes',side_effect=lambda data,name:{'text':data.decode(),'coverage':'full'}) as reader:
            a=office.commit(office.prepare('document_read',{'path':str(p),'start':0,'limit':4}))
            b=self.office().commit(self.office().prepare('document_read',{'path':str(p),'start':4,'limit':4}))
            self.assertEqual((a['content'],b['content']),('abcd','efgh'));self.assertEqual(reader.call_count,1)
            p.write_text('ABCD1234')
            changed=office.commit(office.prepare('document_read',{'path':str(p),'start':0,'limit':4}))
            self.assertEqual(changed['content'],'ABCD');self.assertEqual(reader.call_count,2)
    def test_cached_read_rechecks_root_permission(self):
        p=self.root/'data.txt';p.write_text('hello')
        office=self.office();args={'path':str(p)}
        office.commit(office.prepare('file_read',args))
        plan=office.prepare('file_read',args)
        self.files.roots=[self.root/'different']
        with self.assertRaises(PermissionError):office.commit(plan)
    def test_calculation_reuses_exact_inputs_but_never_current_time(self):
        office=self.office();args={'operation':'convert','value':2,'from_unit':'km','to_unit':'m'}
        first=office.commit(office.prepare('calculate',args))
        reused=self.office().commit(self.office().prepare('calculate',args))
        self.assertEqual(reused['result'],first['result']);self.assertTrue(reused['cached'])
        changed=office.commit(office.prepare('calculate',dict(args,value=3)))
        self.assertNotIn('cached',changed)
        self.assertIsNone(office.cache_key(office.prepare('calculate',{'operation':'now'})))
    def test_read_cache_is_account_isolated_and_implementation_sensitive(self):
        p=self.root/'data.txt';p.write_text('hello');args={'path':str(p)}
        office=self.office();office.commit(office.prepare('file_read',args))
        second=self.office();self.assertTrue(second.commit(second.prepare('file_read',args))['cached'])
        second.cache_version='new-reader-version'
        self.assertNotIn('cached',second.commit(second.prepare('file_read',args)))
        other=self.office(account_scope('other','https://server'))
        self.assertNotIn('cached',other.commit(other.prepare('file_read',args)))
    def test_cache_clear_keeps_other_account(self):
        self.cache.put(self.scope,'k','1',7);self.cache.put('other','k','1',9)
        self.cache.clear(self.scope)
        self.assertIsNone(self.cache.get(self.scope,'k','1'));self.assertEqual(self.cache.get('other','k','1'),9)
    def test_checkpoint_is_evidence_not_replay_and_contains_no_code_or_token(self):
        memory=WorkflowMemory(self.cache);state={'account_username':'owner'};cfg={'server_url':'https://server'}
        call={'function':{'name':'vba_execute','arguments':{'code':'secret macro code','token':'secret token'}}}
        memory.observe(state,cfg,'chat',call,{'ok':False,'uncertain':True,'error':'secret token'})
        text=memory.context(state,cfg,'chat')
        self.assertIn('uncertain',text);self.assertIn('Không phát lại',text)
        with self.cache.connection() as db:data=' '.join(r[0] for r in db.execute('SELECT data FROM cache'))
        self.assertNotIn('secret macro code',data);self.assertNotIn('secret token',data)
        self.assertEqual(memory.context({'account_username':'other'},cfg,'chat'),'')
    def test_inventory_reuses_valid_paths_but_rescans_changed_executable(self):
        from assistant.installed_apps import installed_apps
        exe=self.root/'Plaxis2DXInput.exe';exe.write_bytes(b'original')
        rows=[{'name':'PLAXIS','path':str(exe)}]
        with patch('assistant.installed_apps.os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':'fixture'})),patch('assistant.runtime_cache.optional_cache',return_value=self.cache),patch('assistant.installed_apps._discover_installed_apps',return_value=rows) as scan:
            self.assertEqual(installed_apps(),rows);self.assertEqual(installed_apps(),rows);self.assertEqual(scan.call_count,1)
            exe.write_bytes(b'changed executable')
            installed_apps();self.assertEqual(scan.call_count,2)
            installed_apps(refresh=True);self.assertEqual(scan.call_count,3)

    def test_cache_hit_does_not_bypass_stop(self):
        from assistant.windows_apps import stop_automation
        office=self.office();args={'operation':'expression','expression':'2+2'}
        office.commit(office.prepare('calculate',args))
        stop_automation()
        try:
            with self.assertRaises(PermissionError):office.commit(office.prepare('calculate',args))
        finally:resume_automation()
    def test_workflow_cache_does_not_fail_operation_on_non_json_metadata(self):
        memory=WorkflowMemory(self.cache)
        memory.observe({}, {},'chat',{'function':{'name':'example','arguments':{'value':object()}}},{'ok':True})
    def test_failed_command_reason_available_in_new_conversation_context(self):
        memory=WorkflowMemory(self.cache);cfg={'server_url':'https://server'};state={'account_username':'owner'}
        memory.observe(state,cfg,'old',{'function':{'name':'plaxis_commands','arguments':{}}},{'ok':False,'error':'Unsuccessful command: Invalid parameters'})
        self.assertIn('invalid_parameters',memory.context(state,cfg,'new'))
    def test_local_calculation_cache_and_live_time(self):
        from assistant.runtime_cache import cached_calculate
        args={'operation':'expression','expression':'2+2'}
        first=cached_calculate(args,self.cache,self.scope)
        second=cached_calculate(args,self.cache,self.scope)
        self.assertEqual(first['result'],second['result']);self.assertTrue(second['cached'])
        with patch('assistant.calculator.calculate',return_value={'ok':True,'datetime':'live'}) as calc:
            cached_calculate({'operation':'now'},self.cache,self.scope)
            cached_calculate({'operation':'now'},self.cache,self.scope)
            self.assertEqual(calc.call_count,2)
