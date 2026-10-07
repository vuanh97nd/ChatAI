import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.memory import PersonalMemory
class MemoryTest(unittest.TestCase):
    def test_persistence_isolation_explicit_and_secret_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite')
            alice=PersonalMemory(store,None,'alice');bob=PersonalMemory(store,None,'bob')
            self.assertIsNone(alice.capture_explicit('Hôm nay tôi đi học'))
            ident=alice.capture_explicit('Hãy ghi nhớ: tôi thích lập trình Python')
            self.assertTrue(ident)
            self.assertEqual(bob.search('Python'),[])
            self.assertEqual(len(PersonalMemory(Store(Path(folder)/'db.sqlite'),None,'alice').search('Python')),1)
            self.assertEqual(alice.search('cấu tạo sao Hỏa'),[])
            with self.assertRaises(ValueError):alice.capture_explicit('Ghi nhớ mật khẩu: secret123')
            alice.delete(ident);self.assertEqual(alice.search('Python'),[])
    def test_embedding_failure_and_server_deleted_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite')
            memory=PersonalMemory(store,None,'alice',True)
            memory.sync_server([{'id':'1','title':'Sở thích','text':'Tôi thích Python'}])
            self.assertEqual(len(memory.search('Python')),1)
            memory.sync_server([]);self.assertEqual(memory.search('Python'),[])
