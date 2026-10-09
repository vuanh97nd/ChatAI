import json
import tempfile
import unittest
from pathlib import Path

from assistant.procedure_memory import ProcedureMemory
from assistant.storage import Store
from assistant.history_sync import HistorySync
from test_history_sync import Backend


class ProcedureMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'a.db');self.memory=ProcedureMemory(self.store)
        self.state={'account_username':'alice','messages':[{'role':'user','content':'Viết đơn Word font Times New Roman 13'}],
                    'running':False,'pending':None,'queue':[]}
        self.call={'function':{'name':'word_create_open','arguments':{'font_name':'Times New Roman','font_size':'13'}}}

    def test_success_recalled_after_restart_but_not_for_another_topic_or_owner(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'document_created':True})
        memory=ProcedureMemory(Store(self.store.path))
        self.assertIn('Times New Roman',memory.context('alice','Viết đơn Word'))
        self.assertEqual(memory.context('bob','Viết đơn Word'),'')
        self.assertEqual(memory.context('alice','thời tiết Hà Nội'),'')

    def test_old_tool_history_is_migrated_once_without_trusting_assistant_claims(self):
        cid=self.store.create(False)
        self.state['messages'] += [{'role':'assistant','content':'','tool_calls':[self.call]},
            {'role':'tool','tool_name':'word_create_open','content':'{"ok":true,"document_created":true}'},
            {'role':'assistant','content':'Đã chạy PLAXIS thành công.'}]
        self.store.save(cid,self.state)
        first=self.memory.export('alice')
        self.store.save(cid,self.store.load(cid))
        self.assertEqual(self.memory.export('alice'),first)
        self.assertEqual(first[0]['tool'],'word_create_open')

    def test_failure_is_not_promoted_to_success_and_unverified_claim_is_not_saved(self):
        self.memory.remember('alice',self.state,self.call,{'ok':False,'error':'Font không hỗ trợ'})
        self.memory.remember('alice',self.state,self.call,{'note':'AI nói đã xong'})
        self.memory.remember('alice',self.state,self.call,{'ok':True,'uncertain':True})
        self.memory.remember('alice',self.state,self.call,{'ok':False,'denied':True})
        self.assertEqual(len(self.memory.records('alice')),1)
        self.assertEqual(self.memory.records('alice')[0]['outcome'],'failed')

    def test_credentials_and_ui_handles_are_removed_without_changing_false(self):
        call={'function':{'name':'plaxis_generate_script','arguments':{'auto_run':False,'session':'private-session',
              'problem':json.dumps({'height':4,'api_key':'private-key'}),'password':'private-password'}}}
        self.memory.remember('alice',self.state,call,{'ok':True})
        record=self.memory.export('alice')[0]
        self.assertNotIn('private-',json.dumps(record))
        self.assertIs(json.loads(record['arguments'])['auto_run'],False)

    def test_credentials_inside_json_arguments_are_removed_from_error_evidence(self):
        call={'function':{'name':'plaxis_generate_script','arguments':{
            'problem':json.dumps({'api_key':'private-nested-key','height':4})}}}
        self.memory.remember('alice',self.state,call,{'ok':False,'error':'Request rejected for private-nested-key'})
        self.assertNotIn('private-nested-key',json.dumps(self.memory.records('alice')))

    def test_cloud_restore_makes_procedure_available_in_a_new_conversation_without_execution(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'document_created':True})
        cid=self.store.create(False);self.store.save(cid,self.state)
        backend=Backend();session={'username':'alice','key':'test','endpoint':'https://example.org'}
        HistorySync(self.store,session,backend).cycle()
        other=Store(Path(self.tmp.name)/'b.db');HistorySync(other,session,backend).cycle()
        self.assertIn('Times New Roman',ProcedureMemory(other).context('alice','Viết đơn Word'))
        restored=other.load(cid)
        self.assertFalse(restored['running']);self.assertEqual(restored['queue'],[])
        self.assertIsNone(restored['pending'])

    def test_failure_links_to_fix_and_guard_checks_matching_environment(self):
        state=dict(self.state,procedure_environment='PLAXIS 2D 22.1')
        failed={'function':{'name':'plaxis_commands','arguments':{'commands':json.dumps([{'command':'set','args':[{'ref':'g.Soil_1'},'Wrong',3]}])}}}
        fixed={'function':{'name':'plaxis_commands','arguments':{'commands':json.dumps([{'command':'set','args':[{'ref':'g.Soil_1'},'Identification','Clay']}])}}}
        self.memory.remember('alice',state,failed,{'ok':False,'error':'Unknown property: Wrong'})
        self.memory.remember('alice',state,fixed,{'ok':True})
        records=self.memory.records('alice');success=next(r for r in records if r['outcome']=='success');failure=next(r for r in records if r['outcome']=='failed')
        self.assertEqual(success['resolves'],[failure['id']])
        self.assertIn('cách sửa',self.memory.preflight('alice',state,failed))
        different=dict(state,procedure_environment='PLAXIS 3D 2024',procedure_guarded=[])
        self.assertIsNone(self.memory.preflight('alice',different,failed))
        self.assertIsNone(self.memory.preflight('bob',dict(state,procedure_guarded=[]),failed))

    def test_partial_batch_preserves_applied_objects_and_uncertain_failed_step(self):
        call={'function':{'name':'plaxis_commands','arguments':{'commands':json.dumps([
            {'command':'soilmat','args':['Identification','Clay']},
            {'command':'set','args':[{'ref':'g.Soil_1'},'Unknown',3]}])}}}
        result={'ok':False,'results':[{'step':1,'command':'soilmat','value':'Clay_1'}],
                'failed_step':2,'error':'Unknown property','uncertain':True}
        self.memory.remember('alice',self.state,call,result)
        rows=self.memory.records('alice');self.assertEqual(len(rows),2)
        progress=self.state['procedure_progress']['steps']
        self.assertEqual(progress[0]['status'],'applied');self.assertIn('Clay_1',progress[0]['identity'])
        self.assertEqual(progress[1]['status'],'uncertain')
        self.assertIn('không chạy lại tự động',next(r for r in rows if r['outcome']=='failed')['evidence'])

    def test_command_success_is_not_complete_model_or_verified_results(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True})
        self.assertEqual(self.memory.records('alice')[0]['level'],'command')
        self.memory.remember('alice',self.state,self.call,{'ok':True,'model_verified':True})
        self.assertEqual(self.memory.records('alice')[0]['level'],'model')
        self.memory.remember('alice',self.state,self.call,{'ok':True,'results_verified':True})
        self.assertEqual(self.memory.records('alice')[0]['level'],'results')

    def test_model_progress_survives_cloud_without_restoring_pending_action(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True})
        cid=self.store.create(False);self.store.save(cid,self.state)
        backend=Backend();session={'username':'alice','key':'test','endpoint':'https://example.org'}
        HistorySync(self.store,session,backend).cycle()
        other=Store(Path(self.tmp.name)/'progress.db');HistorySync(other,session,backend).cycle()
        state=other.load(cid)
        self.assertTrue(state['procedure_progress']['needs_live_check'])
        self.assertEqual(state['procedure_progress']['steps'][0]['status'],'applied')
        self.assertFalse(state['running']);self.assertEqual(state['queue'],[])

    def test_new_metadata_survives_same_timestamp_legacy_snapshot_and_json_spacing(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'model_verified':True})
        full=self.memory.records('alice')[0]
        legacy={k:full[k] for k in ('id','tool','task','arguments','evidence','updated','outcome')}
        other=ProcedureMemory(Store(Path(self.tmp.name)/'new.db'))
        other.import_records('alice',[legacy]);other.import_records('alice',[full]);other.import_records('alice',[legacy])
        self.assertEqual(other.records('alice')[0]['level'],'model')
        self.assertEqual(other.records('alice')[0]['schema_version'],2)
        from assistant.procedure_memory import canonical_arguments
        self.assertEqual(canonical_arguments({'commands':'[{"args":[1],"command":"set"}]'}),
                         canonical_arguments({'commands':'[ { "command": "set", "args": [ 1 ] } ]'}))

    def test_long_checkpoint_keeps_relevant_lessons_and_recent_progress(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'document_created':True})
        self.state['procedure_progress']['steps']=[
            {'tool':'word_create_open','command':'create','status':'applied',
             'identity':str(i),'evidence':'x'*700} for i in range(200)]
        context=self.memory.context('alice','Viết đơn Word',state=self.state)
        payload=json.loads(context.split('\n')[-1])
        self.assertTrue(payload['lessons'])
        self.assertEqual(payload['progress']['steps'][-1]['identity'],'199')
        self.assertLessEqual(len(context),12000)

    def test_new_topic_does_not_include_old_progress_but_acknowledgement_keeps_it(self):
        self.memory.remember('alice',self.state,self.call,{'ok':True,'document_created':True})
        self.assertEqual(self.memory.context('alice','Thời tiết Hà Nội',state=self.state),'')
        self.assertEqual(self.memory.context('alice','hi',state=self.state),'')
        self.assertIn('Times New Roman',self.memory.context('alice','ok',state=self.state))

    def test_fix_after_cloud_restore_links_the_previous_failure_for_admin_training(self):
        state=dict(self.state,account_username='admin',procedure_environment='PLAXIS 2D 22.1')
        failed={'function':{'name':'plaxis_commands','arguments':{'commands':json.dumps([
            {'command':'set','args':[{'ref':'g.Soil_1'},'Wrong',3]}])}}}
        fixed={'function':{'name':'plaxis_commands','arguments':{'commands':json.dumps([
            {'command':'set','args':[{'ref':'g.Soil_1'},'Identification','Clay']}])}}}
        self.memory.remember('admin',state,failed,{'ok':False,'error':'Unknown property: Wrong'})
        cid=self.store.create(False);self.store.save(cid,state)
        backend=Backend();session={'username':'admin','key':'test','endpoint':'https://example.org'}
        HistorySync(self.store,session,backend).cycle()
        other=Store(Path(self.tmp.name)/'admin-restored.db');HistorySync(other,session,backend).cycle()
        restored=other.load(cid);memory=ProcedureMemory(other)
        memory.remember('admin',restored,fixed,{'ok':True},training=True)
        records=memory.records('admin');success=next(r for r in records if r['outcome']=='success');failure=next(r for r in records if r['outcome']=='failed')
        self.assertEqual(success['resolves'],[failure['id']])
        self.assertTrue(failure['training']);self.assertTrue(success['training'])
