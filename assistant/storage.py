import json
import os
import hashlib
from pathlib import Path
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, default=str)


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        original=Path(path)
        if os.name=='nt' and os.environ.get('LOCALAPPDATA'):
            project_id=hashlib.sha256(str(original.resolve()).casefold().encode()).hexdigest()[:12]
            folder=Path(os.environ['LOCALAPPDATA'])/'ChatAI'/'data'/project_id
            folder.mkdir(parents=True,exist_ok=True)
            local=folder/'history.sqlite3'
            if not local.exists() and original.exists():
                temp=folder/'history.migrating.sqlite3'
                try:
                    source=sqlite3.connect(original.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
                    destination=sqlite3.connect(temp)
                    try:
                        deadline=__import__('time').monotonic()+30
                        def check_progress(status,remaining,total):
                            if __import__('time').monotonic()>deadline:raise TimeoutError('Nhập lịch sử quá thời gian.')
                        source.backup(destination,pages=128,progress=check_progress,sleep=.1)
                        if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                            raise RuntimeError('Cơ sở dữ liệu cũ cần phục hồi.')
                    finally:destination.close();source.close()
                    temp.replace(local)
                except Exception as error:
                    temp.unlink(missing_ok=True)
                    raise RuntimeError('Không nhập được lịch sử từ Google Drive. Chọn “Available offline” cho thư mục Chat-AI, chờ đồng bộ rồi mở lại. Dữ liệu cũ vẫn được giữ nguyên. '+str(error)) from error
            self.path=str(local)
            print('SQLite local: '+self.path,flush=True)
        else:
            self.path=str(original)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    updated TEXT NOT NULL, state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL, conversation_id TEXT NOT NULL,
                    action TEXT NOT NULL, details TEXT NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, persist=True):
        cid = uuid.uuid4().hex
        if persist:
            state = {"messages": [], "queue": [], "pending": None,
                     "running": False, "rounds": 0, "model": None}
            with self.connection() as db:
                db.execute("INSERT INTO conversations VALUES (?,?,?,?)",
                           (cid, "Cuộc trò chuyện mới", now(), dumps(state)))
        return cid

    def list(self, owner=None, include_empty=True):
        with self.connection() as db:
            rows=db.execute("SELECT id,title,state FROM conversations ORDER BY updated DESC").fetchall()
        result=[]
        for cid,title,raw in rows:
            state=json.loads(raw)
            if not include_empty and not state.get('messages') and not state.get('pending') and not state.get('queue'):
                continue
            if owner is None or state.get('account_username')==owner:result.append((cid,title))
        return result

    def load(self, cid):
        with self.connection() as db:
            row = db.execute("SELECT state FROM conversations WHERE id=?", (cid,)).fetchone()
        if not row:
            # Mã hội thoại mới chỉ được ghi xuống SQLite sau khi có tin nhắn.
            return {"messages": [], "queue": [], "pending": None,
                    "running": False, "rounds": 0, "model": None}
        return json.loads(row[0])

    def save(self, cid, state):
        title = next((m["content"][:60] for m in state["messages"] if m["role"] == "user"),
                     "Cuộc trò chuyện mới")
        with self.connection() as db:
            db.execute("INSERT INTO conversations(id,title,updated,state) VALUES (?,?,?,?) "
                       "ON CONFLICT(id) DO UPDATE SET title=excluded.title,updated=excluded.updated,state=excluded.state",
                       (cid,title,now(),dumps(state)))

    def remember_conversation(self, username, cid):
        state=self.load(cid)
        if state.get('account_username') not in (None,username):return
        if not state.get('messages') and not state.get('pending') and not state.get('queue'):
            return
        if not state.get('account_username'):
            state['account_username']=username
            self.save(cid,state)
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)',('last_conversation:'+username,cid))

    def last_conversation(self, username):
        with self.connection() as db:
            row=db.execute('SELECT value FROM settings WHERE key=?',('last_conversation:'+username,)).fetchone()
            if row:
                saved=db.execute('SELECT state FROM conversations WHERE id=?',(row[0],)).fetchone()
                if saved:
                    state=json.loads(saved[0])
                    if state.get('account_username')==username and state.get('messages'):return row[0]
            rows=db.execute('SELECT id,state FROM conversations ORDER BY updated DESC').fetchall()
        for cid,raw in rows:
            state=json.loads(raw)
            if state.get('account_username')==username and state.get('messages'):return cid
        return None

    def audit(self, cid, action, details):
        with self.connection() as db:
            db.execute("INSERT INTO audit(at,conversation_id,action,details) VALUES (?,?,?,?)",
                       (now(), cid, action, dumps(details)))

    def recent_audit(self, cid):
        with self.connection() as db:
            rows = db.execute("SELECT at,action,details FROM audit WHERE conversation_id=? "
                              "ORDER BY id DESC LIMIT 30", (cid,)).fetchall()
        return [{"at": r[0], "action": r[1], "details": json.loads(r[2])} for r in rows]

    def delete(self, cid, backups):
        """UI đã xác nhận; backup hội thoại trước DELETE, giữ audit."""
        folder = Path(backups); folder.mkdir(parents=True, exist_ok=True)
        backup = folder / f'conversation_{cid}_{uuid.uuid4().hex[:8]}.json'
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT title,updated,state FROM conversations WHERE id=?', (cid,)).fetchone()
            if row is None: raise KeyError('Hội thoại không còn tồn tại.')
            snapshot = {'id': cid, 'title': row[0], 'updated': row[1], 'state': json.loads(row[2])}
            with backup.open('x', encoding='utf-8') as out: out.write(dumps(snapshot))
            db.execute('DELETE FROM conversations WHERE id=?', (cid,))
            db.execute('INSERT INTO audit(at,conversation_id,action,details) VALUES (?,?,?,?)',
                       (now(), cid, 'conversation_deleted', dumps({'backup': str(backup)})))
        return str(backup)
