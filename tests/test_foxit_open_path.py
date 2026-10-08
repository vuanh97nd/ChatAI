import unittest
from unittest.mock import Mock,patch
from assistant.foxit_ocr_automation import _submit_pdf_path,_filename_edit

class FoxitOpenPathTests(unittest.TestCase):
    def test_full_unicode_filename_verified_before_open(self):
        path='G:\\My Drive\\Đề bài\\Plaxis.pdf'
        edit=Mock();edit.get_value.return_value=path
        button=Mock();dialog=Mock();dialog.child_window.return_value=button
        with patch('assistant.foxit_ocr_automation._filename_edit',return_value=edit):
            _submit_pdf_path(dialog,path)
        edit.set_edit_text.assert_called_once_with(path)
        button.click_input.assert_called_once()
        dialog.child_window.assert_called_once_with(auto_id='1',control_type='Button')
    def test_empty_filename_never_confirms_folder(self):
        edit=Mock();edit.get_value.return_value=''
        dialog=Mock()
        with patch('assistant.foxit_ocr_automation._filename_edit',return_value=edit):
            with self.assertRaisesRegex(RuntimeError,'chưa bấm Open'):_submit_pdf_path(dialog,'G:\\file.pdf')
        dialog.child_window.assert_not_called()
    def test_combo_child_edit_is_used_when_1148_is_not_an_edit(self):
        combo=Mock();direct=Mock();direct.exists.return_value=False
        inner=Mock();inner.exists.return_value=True;combo.child_window.return_value=inner
        dialog=Mock()
        dialog.child_window.side_effect=lambda **kw:combo if kw.get('control_type')=='ComboBox' else direct
        self.assertIs(_filename_edit(dialog),inner.wrapper_object.return_value)
        self.assertTrue(all(call.kwargs.get('auto_id') in ('1148','1001') for call in dialog.child_window.call_args_list))
    def test_open_pdf_passes_full_path_as_one_argument_without_dialog(self):
        import tempfile
        from pathlib import Path
        from assistant.foxit_ocr_automation import _open_file
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'Đề bài PLAXIS.pdf';source.write_bytes(b'%PDF-test')
            app=Mock();app.window.return_value.exists.return_value=False
            window=Mock();window.window_text.return_value=source.name+' - Foxit PDF Editor'
            with patch('subprocess.Popen') as launch,patch('assistant.foxit_ocr_automation._wait_for_main_window',return_value=window),patch('assistant.foxit_ocr_automation._fill_open_dialog') as fill:
                _open_file(app,str(source),exe='/apps/Foxit Editor/FoxitPDFEditor.exe')
            launch.assert_called_once_with(['/apps/Foxit Editor/FoxitPDFEditor.exe',str(source.resolve())],cwd='/apps/Foxit Editor',shell=False)
            fill.assert_not_called()
    def test_missing_source_is_not_opened_as_folder(self):
        from assistant.foxit_ocr_automation import _open_file
        with patch('subprocess.Popen') as launch:
            with self.assertRaisesRegex(RuntimeError,'PDF tồn tại'):
                _open_file(Mock(),'/missing/file.pdf',exe='/apps/Foxit.exe')
            launch.assert_not_called()

    def test_document_verification_accepts_hidden_extension_and_selected_tab(self):
        from pathlib import Path
        from assistant.foxit_ocr_automation import _pdf_window_matches
        source=Path('3D-1-Tutorial.pdf')
        window=Mock();window.window_text.return_value='3D-1-Tutorial - Foxit PDF Editor'
        self.assertTrue(_pdf_window_matches(window,source))
        window.window_text.return_value='Start - Foxit PDF Editor'
        tab=Mock();tab.window_text.return_value='3D-1-Tutorial.pdf';tab.is_selected.return_value=True
        window.descendants.return_value=[tab]
        self.assertTrue(_pdf_window_matches(window,source))
        tab.is_selected.return_value=False
        self.assertFalse(_pdf_window_matches(window,source))
    def test_native_dialog_uses_filename_combo_not_address_bar(self):
        from assistant.foxit_ocr_automation import _submit_native_dialog
        dialog=Mock();combo=Mock();edit=Mock();button=Mock()
        dialog.child_window.side_effect=lambda **kw:combo if kw['control_id']==1148 else button
        combo.child_window.return_value.wrapper_object.return_value=edit
        path='G:\\My Drive\\3D-1-Tutorial.pdf';edit.window_text.return_value=path
        _submit_native_dialog(dialog,path)
        combo.child_window.assert_called_once_with(class_name='Edit')
        edit.set_edit_text.assert_called_once_with(path);button.click.assert_called_once()
        edit.window_text.return_value=''
        button.reset_mock()
        with self.assertRaisesRegex(RuntimeError,'chưa bấm Open'):_submit_native_dialog(dialog,path)
        button.click.assert_not_called()
