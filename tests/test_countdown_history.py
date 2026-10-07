import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from assistant.storage import Store


class HistoryUndoTest(unittest.TestCase):
    def test_delete_restore_preserves_history_title_and_generated_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=Store(root/'history.db');cid=store.create(persist=False)
            document=root/'drawing.dxf';document.write_text('keep')
            state=store.load(cid);state.update(account_username='alice',custom_title='Bản vẽ',messages=[{'role':'user','content':'vẽ hình'}],generated_files=[str(document)])
            store.save(cid,state)
            backup=store.delete(cid,root/'backups')
            self.assertEqual(store.list('alice'),[])
            with self.assertRaises(PermissionError):store.restore_deleted(backup,'bob')
            store.restore_deleted(backup,'alice')
            self.assertEqual(store.load(cid),state)
            self.assertEqual(store.list('alice')[0][1],'Bản vẽ')
            self.assertEqual(document.read_text(),'keep')
            with self.assertRaises(ValueError):store.restore_deleted(backup,'alice')


class CountdownTest(unittest.TestCase):
    def test_three_second_countdown_runs_once_before_action(self):
        from desktop_ui import Worker
        worker=Worker(lambda emit:None);worker.cancellable=True;worker.app_countdown=True
        worker.stop_requested=Mock();worker.stop_requested.is_set.return_value=False;worker.stop_requested.wait.return_value=False
        events=[];worker.event.connect(events.append)
        worker.emit_event({'type':'app_activity','text':'mở Word'})
        worker.emit_event({'type':'app_activity','text':'viết tài liệu'})
        self.assertEqual([e['seconds'] for e in events if e['type']=='app_countdown'],[3,2,1,0])
        self.assertEqual(worker.stop_requested.wait.call_count,3)
        worker.stop_requested.wait.assert_called_with(1)
        self.assertEqual(events[4]['type'],'app_activity')

    def test_cancel_during_countdown_never_emits_action(self):
        from desktop_ui import Worker,ChatCancelled
        worker=Worker(lambda emit:None);worker.cancellable=True;worker.app_countdown=True
        worker.stop_requested=Mock();worker.stop_requested.is_set.return_value=False;worker.stop_requested.wait.return_value=True
        events=[];worker.event.connect(events.append)
        with self.assertRaises(ChatCancelled):worker.emit_event({'type':'app_activity','text':'mở Word'})
        self.assertEqual(events,[{'type':'app_countdown','seconds':3}])
