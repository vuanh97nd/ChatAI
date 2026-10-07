import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from assistant import ollama_setup as setup


class OllamaSetupTest(unittest.TestCase):
    def test_running_service_does_not_install(self):
        with patch.object(setup,'WINDOWS',True),patch.object(setup,'service_ready',return_value=True),patch.object(setup,'find_executable') as find:
            setup.ensure_ollama(Mock(host='http://127.0.0.1:11434'),Path('.'),Mock())
            find.assert_not_called()

    def test_remote_service_disallowed(self):
        with self.assertRaises(ValueError):setup.service_ready('https://example.com')

    def test_unsigned_installer_never_passes_verification(self):
        with patch.object(setup.subprocess,'run',return_value=Mock(returncode=1)):
            with self.assertRaises(RuntimeError):setup.verify_installer(Path('installer.exe'))

    def test_existing_install_starts_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/'ollama.exe';exe.touch()
            with patch.object(setup,'WINDOWS',True),patch.dict(setup.os.environ,{'LOCALAPPDATA':directory,'GGML_CUDA_PDL':'0'}),patch.object(setup,'service_ready',side_effect=[False,False,True]),patch.object(setup,'find_executable',return_value=exe),patch.object(setup,'download_installer') as download,patch.object(setup.subprocess,'Popen') as process:
                setup.ensure_ollama(Mock(host='http://127.0.0.1:11434'),Path(directory),Mock())
                download.assert_not_called()
                self.assertEqual(process.call_args.args[0],[str(exe),'serve'])
                self.assertEqual(process.call_args.kwargs['env']['GGML_CUDA_PDL'],'0')

    def test_download_install_before_service_start(self):
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/'ollama.exe';exe.touch();order=[]
            def downloaded(path,progress):path.write_bytes(b'installer');order.append('download')
            with patch.object(setup,'WINDOWS',True),patch.dict(setup.os.environ,{'LOCALAPPDATA':directory,'GGML_CUDA_PDL':'0'}),patch.object(setup,'service_ready',side_effect=[False,False,True]),patch.object(setup,'find_executable',side_effect=[None,exe]),patch.object(setup.shutil,'disk_usage',return_value=Mock(free=10*1024**3)),patch.object(setup,'download_installer',side_effect=downloaded),patch.object(setup,'verify_installer',side_effect=lambda p:order.append('verify')),patch.object(setup.subprocess,'run',side_effect=lambda *a,**k:(order.append('install') or Mock(returncode=0))),patch.object(setup.subprocess,'Popen',side_effect=lambda *a,**k:(order.append('start') or Mock())):
                setup.ensure_ollama(Mock(host='http://127.0.0.1:11434'),Path(directory),Mock())
                self.assertEqual(order,['download','verify','install','start'])
