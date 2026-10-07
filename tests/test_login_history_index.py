import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from assistant.storage import Store
from assistant.trial import GuestTrial


class LoginHistoryIndexTest(unittest.TestCase):
    def test_existing_history_is_indexed_and_adoption_keeps_other_accounts(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'history.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,updated TEXT NOT NULL,state TEXT NOT NULL)')
                rows=[(str(i),'History '+str(i),str(i).zfill(6),json.dumps({'account_username':'bob','messages':[{'role':'user','content':'large history '*500}],'custom_title':'kept'})) for i in range(200)]
                rows.append(('guest','Guest','000201',json.dumps({'account_username':':guest:','messages':[{'role':'user','content':'Hello'}],'custom_title':'Guest custom'})))
                db.executemany('INSERT INTO conversations VALUES(?,?,?,?)',rows)
            store=Store(path)
            with store.connection() as db:
                query="SELECT id,title FROM conversations WHERE json_extract(state,'$.account_username')=? ORDER BY updated DESC LIMIT 100"
                plan=db.execute('EXPLAIN QUERY PLAN '+query,('bob',)).fetchall()
                self.assertTrue(any('USING INDEX conversations_owner_updated' in str(row) for row in plan))
                adoption=db.execute("EXPLAIN QUERY PLAN UPDATE conversations SET state=json_set(state,'$.account_username',?) WHERE json_extract(state,'$.account_username')=?",('alice',':guest:')).fetchall()
                self.assertTrue(any('USING INDEX conversations_owner_updated' in str(row) for row in adoption))
            GuestTrial(store).adopt('alice')
            self.assertEqual(store.list('alice'),[('guest','Guest')])
            self.assertEqual(len(store.list('bob')),200)
            self.assertEqual(store.load('guest')['custom_title'],'Guest custom')
            Store(path) # repeated startup preserves index and data
            self.assertEqual(store.load('0')['custom_title'],'kept')
