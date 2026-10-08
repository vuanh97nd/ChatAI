"""Library integration must preserve attachment reader options and results."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from assistant.library_hooks import _wrap_read_attachments

class AttachmentHookTest(unittest.TestCase):
    def test_online_and_local_options_reach_reader_and_library(self):
        for args,kwargs in [((),{}),((),{'online':True}),((True,),{})]:
            with self.subTest(args=args,kwargs=kwargs):
                items=[{'source':'document.pdf','content':'text'}]
                original=Mock(return_value=items);win=SimpleNamespace(read_attachments=original)
                library=Mock();library.remember.return_value=True;progress=Mock()
                with patch('assistant.library_hooks.library_for',return_value=library),patch('assistant.library_hooks.background') as background:
                    _wrap_read_attachments(win)
                    result=win.read_attachments(['document.pdf'],progress,*args,**kwargs)
                original.assert_called_once_with(['document.pdf'],progress,*args,**kwargs)
                self.assertIs(result,items)
                library.remember.assert_called_once_with(items[0],'document.pdf')
                background.assert_called_once_with(win)
                progress.assert_called_once()
    def test_reader_error_is_not_hidden_or_remembered(self):
        win=SimpleNamespace(read_attachments=Mock(side_effect=ValueError('Invalid document')))
        with patch('assistant.library_hooks.library_for') as library:
            _wrap_read_attachments(win)
            with self.assertRaisesRegex(ValueError,'Invalid document'):
                win.read_attachments(['bad.pdf'],online=True)
        library.assert_not_called()
