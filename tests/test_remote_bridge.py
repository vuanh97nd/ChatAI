import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from assistant.remote_bridge import RemoteChannel, existing_plaxis_input
from assistant.remote_ui import RemoteMixin

TASK={'id':'fixture-task','lease_id':'fixture-lease','prompt':'Read Excel'}
class RemoteChannelTests(unittest.TestCase):
    def make(self, responses):
        request=Mock(side_effect=responses)
        channel=RemoteChannel({'username':'alice','key':'session:fixture','endpoint':'https://example.org'},
                              {'desktop_id':'desktop','desktop_secret':'private'},request=request)
        events=[];channel.event.connect(events.append)
        return channel,request,events
    def test_claim_delivered_once_and_terminal_ack_releases_local_slot(self):
        channel,request,events=self.make([
            {'task':TASK,'active':None,'pairs':[]},
            {'task':None,'active':{**TASK,'state':'running'},'pairs':[]},
            {'task':None,'active':None,'pairs':[]},
        ])
        channel.set_ready(True);channel.tick()
        channel.report('running','Reading');channel.tick()
        channel.report('completed','Done','Result');channel.tick()
        self.assertEqual(len([e for e in events if e['type']=='task']),1)
        self.assertEqual([e['id'] for e in events if e['type']=='ack'],['fixture-task'])
        self.assertIsNone(channel.current)
        self.assertFalse(request.call_args.kwargs['ready'])
    def test_control_ack_survives_progress_updates_before_network_tick(self):
        channel,request,events=self.make([{'task':TASK,'active':None,'pairs':[]}])
        channel.tick();channel.report('running','Stopping',ack='pause')
        channel.report('paused','Stopped','Partial result')
        self.assertEqual(channel.update['ack'],'pause')
    def test_restart_does_not_replay_claim_and_keeps_server_version(self):
        channel,request,events=self.make([{'task':None,'active':{**TASK,'state':'running','version':50},'pairs':[]}])
        channel.tick();channel.report('failed','Previous process unknown')
        self.assertEqual(events[-1]['type'],'orphan')
        self.assertEqual(channel.update['version'],51)
        self.assertFalse(any(e['type']=='task' for e in events))
    def test_commands_not_repeated_until_server_ack_then_new_command_allowed(self):
        active={**TASK,'state':'running','command':'pause'}
        channel,request,events=self.make([
            {'task':TASK,'active':None,'pairs':[]},
            {'active':active,'pairs':[]},{'active':active,'pairs':[]},
            {'active':{**active,'command':None},'pairs':[]},
            {'active':active,'pairs':[]},
        ])
        for _ in range(5):channel.tick()
        self.assertEqual(len([e for e in events if e['type']=='command']),2)
    def test_open_plaxis_is_detected_before_phone_job(self):
        with patch('psutil.process_iter',return_value=[SimpleNamespace(info={'name':'Plaxis2DInput.exe'})]):
            self.assertTrue(existing_plaxis_input())
        with patch('psutil.process_iter',return_value=[SimpleNamespace(info={'name':'notepad.exe'})]):
            self.assertFalse(existing_plaxis_input())

class RemoteUITests(unittest.TestCase):
    def test_busy_desktop_never_changes_local_chat_or_executes_claim(self):
        ui=RemoteMixin();ui.remote_channel=Mock();ui.busy=lambda:True
        ui.new_chat=Mock();ui.send=Mock()
        ui.remote_accept(TASK)
        ui.new_chat.assert_not_called();ui.send.assert_not_called()
        self.assertEqual(ui.remote_channel.report.call_args.args[0],'failed')
    def test_remote_progress_does_not_capture_other_local_conversation(self):
        ui=RemoteMixin();ui.remote_task={'cid':'remote'};ui.remote_channel=Mock()
        ui.worker=SimpleNamespace(chat_cid='local')
        ui.remote_progress({'type':'status','text':'Local data'})
        ui.remote_channel.report.assert_not_called()
        ui.worker.chat_cid='remote';ui.remote_progress({'type':'status','text':'Remote progress'})
        ui.remote_channel.report.assert_called_once_with('running','Remote progress')
    def test_existing_plaxis_model_prevents_execution(self):
        ui=RemoteMixin();ui.remote_channel=Mock();ui.busy=lambda:False
        ui.input=Mock();ui.input.toPlainText.return_value=''
        ui.new_chat=Mock();ui.send=Mock()
        with patch('assistant.remote_ui.existing_plaxis_input',return_value=True):
            ui.remote_accept({**TASK,'prompt':'Run PLAXIS tutorial'})
        ui.send.assert_not_called();ui.new_chat.assert_not_called()
        self.assertIn('PLAXIS',ui.remote_channel.report.call_args.args[1])

if __name__=='__main__':unittest.main()
