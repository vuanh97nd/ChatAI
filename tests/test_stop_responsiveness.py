import threading
import unittest
from types import SimpleNamespace
from assistant.cloud import cancellable_request,CloudError


class StopTest(unittest.TestCase):
    def test_cancel_returns_before_blocked_model_response(self):
        cancel=threading.Event();started=threading.Event();release=threading.Event();finished=threading.Event();errors=[]
        def request():
            started.set();release.wait(2);return {'answer':'late result'}
        def task():
            try:cancellable_request(request,cancel)
            except CloudError as error:errors.append(str(error))
            finally:finished.set()
        thread=threading.Thread(target=task);thread.start()
        try:
            self.assertTrue(started.wait(1));cancel.set()
            self.assertTrue(finished.wait(.5));self.assertEqual(errors,['Đã dừng yêu cầu.'])
        finally:release.set();thread.join(1)

    def test_transport_errors_are_preserved(self):
        def request():raise ValueError('network fixture')
        with self.assertRaisesRegex(ValueError,'network fixture'):cancellable_request(request,threading.Event())

    def test_stop_app_also_cancels_current_worker(self):
        from desktop_ui import Window
        from assistant.windows_apps import resume_automation
        worker=SimpleNamespace(cancellable=True,stop_requested=threading.Event())
        host=SimpleNamespace(worker=worker,cfg={},status=SimpleNamespace(setText=lambda text:None))
        try:
            Window.stop_windows_apps(host)
            self.assertTrue(worker.stop_requested.is_set())
        finally:resume_automation()

    def test_close_requests_stop_instead_of_blocking_dialog(self):
        from desktop_ui import Window
        from unittest.mock import Mock
        host=SimpleNamespace(worker=SimpleNamespace(cancellable=True),busy=lambda:True,
                             send_or_stop=Mock(),status=SimpleNamespace(setText=lambda text:None))
        event=Mock();Window.closeEvent(host,event)
        self.assertTrue(host.exit_when_idle);host.send_or_stop.assert_called_once()
        event.ignore.assert_called_once()
