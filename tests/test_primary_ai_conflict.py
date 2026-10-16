import ast
import unittest
from scripts.resolve_primary_ai_cherry_pick import integrate


class PrimaryAIConflictTests(unittest.TestCase):
    def test_preserves_extra_local_features_while_removing_backup_actions(self):
        source='''class Window:
    def setup(self):
        self.keep_local_feature()
<<<<<<< HEAD
        self.button(box,'AI backup',self.backup_login_dialog)
        self.button(box,'Local API',self.custom_local_api_dialog)
=======
>>>>>>> 60d9921 (Remove AI backup configuration and keep online AI on primary)
        self.keep_payments()
    def backup_login_dialog(self):
        pass
    def custom_local_api_dialog(self):
        self.keep_direct_settings()
'''
        result=integrate(source)
        ast.parse(result)
        self.assertIn('self.keep_local_feature()',result)
        self.assertIn('self.keep_payments()',result)
        self.assertIn('self.custom_local_api_dialog',result)
        self.assertNotIn('backup_login_dialog',result)

    def test_other_conflicts_are_refused(self):
        with self.assertRaises(ValueError):
            integrate('<<<<<<< HEAD\nx=1\n=======\nx=2\n>>>>>>> unrelated\n')

    def test_handles_diff3_and_is_repeatable(self):
        source='x=1\n<<<<<<< HEAD\ny=2\n||||||| base\ny=0\n=======\ny=3\n>>>>>>> 60d9921 (Remove AI backup)\n'
        result=integrate(source)
        self.assertEqual(result,'x=1\ny=2\n')
        self.assertEqual(integrate(result),result)
        self.assertEqual(integrate(source.replace('\n','\r\n')),result)

    def test_syntax_error_stops_before_writing(self):
        with self.assertRaises(SyntaxError):integrate('def broken(\n')


class MultiFilePrimaryAIConflictTests(unittest.TestCase):
    def test_backend_conflicts_use_primary_only_change_and_keep_unrelated_code(self):
        from scripts.resolve_primary_ai_cherry_pick import resolve_markers
        source="local_feature=123\n<<<<<<< HEAD\ndef ai_request():\n    return backup()\n=======\ndef ai_request():\n    return primary()\n>>>>>>> 60d9921 (Remove AI backup)\nkeep_payments=True\n"
        result=resolve_markers(source)
        compile(result,'assistant/failover.py','exec')
        self.assertIn('return primary()',result)
        self.assertNotIn('return backup()',result)
        self.assertIn('local_feature=123',result)
        self.assertIn('keep_payments=True',result)

    def test_preflight_error_does_not_write_or_stage_any_file(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts.resolve_primary_ai_cherry_pick import repair
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'assistant').mkdir()
            desktop=root/'desktop_ui.py';desktop.write_text('<<<<<<< HEAD\nx=1\n=======\nx=2\n>>>>>>> 60d9921 (Remove AI backup)\n')
            backend=root/'assistant/failover.py';backend.write_text('def broken(\n')
            original=desktop.read_bytes()
            def git(args,**kwargs):
                if args[1]=='diff-tree':return b'desktop_ui.py\nassistant/failover.py\n'
                return b'desktop_ui.py\nassistant/failover.py\n'
            with patch('scripts.resolve_primary_ai_cherry_pick.subprocess.check_output',side_effect=git),patch('scripts.resolve_primary_ai_cherry_pick.subprocess.check_call') as stage:
                with self.assertRaises(SyntaxError):repair(root)
                stage.assert_not_called()
            self.assertEqual(desktop.read_bytes(),original)
            self.assertFalse((root/'data').exists())

    def test_success_backs_up_and_resolves_desktop_and_backend_together(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts.resolve_primary_ai_cherry_pick import repair
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'assistant').mkdir()
            desktop=root/'desktop_ui.py';desktop.write_text('class Window:\n    def setup(self):\n<<<<<<< HEAD\n        self.backup_login_dialog()\n        self.keep_local()\n=======\n        self.keep_local()\n>>>>>>> 60d9921 (Remove AI backup)\n')
            backend=root/'assistant/failover.py';backend.write_text('<<<<<<< HEAD\ndef ai_request():\n    return backup()\n=======\ndef ai_request():\n    return primary()\n>>>>>>> 60d9921 (Remove AI backup)\n')
            originals={p:p.read_bytes() for p in (desktop,backend)}
            def git(args,**kwargs):
                if args[1]=='diff-tree':return b'desktop_ui.py\nassistant/failover.py\n'
                if args[1]=='rev-parse':return b'.git/CHERRY_PICK_HEAD\n'
                return b''
            with patch('scripts.resolve_primary_ai_cherry_pick.subprocess.check_output',side_effect=git),patch('scripts.resolve_primary_ai_cherry_pick.subprocess.check_call') as stage:
                repair(root)
                self.assertEqual(stage.call_args.args[0],['git','add','--','assistant/failover.py','desktop_ui.py'])
            for path,original in originals.items():
                self.assertNotIn('>>>>>>>',path.read_text())
                compile(path.read_text(),str(path),'exec')
                backup=list((root/'data').glob('primary-ai-conflict-*'))[0]/path.relative_to(root)
                self.assertEqual(backup.read_bytes(),original)
            self.assertIn('self.keep_local()',desktop.read_text())
            self.assertIn('return primary()',backend.read_text())


class RemovedBackupCallbackTests(unittest.TestCase):
    def test_startup_settings_never_binds_removed_global_callback(self):
        # The import was already removed by the cherry-pick, but the local UI
        # kept a global callback. Compile alone cannot catch this NameError.
        source='''class Window:
    def __init__(self):
        self.buttons=[]
        self.build_settings()
    def button(self,box,label,callback):
        self.buttons.append((label,callback))
    def build_settings(self):
        box=object()
        self.button(box,'Tắt AI dự phòng',forget_backup)
        self.button(box,'Kết nối AI dự phòng',self.backup_login_dialog)
        self.button(box,'Thanh toán',self.open_billing)
    def backup_login_dialog(self):
        pass
    def open_billing(self):
        return 'payments intact'
'''
        result=integrate(source)
        namespace={};exec(compile(result,'desktop_ui.py','exec'),namespace)
        window=namespace['Window']()
        self.assertEqual([label for label,callback in window.buttons],['Thanh toán'])
        self.assertEqual(window.buttons[0][1](),'payments intact')
        self.assertNotIn('forget_backup',result)
