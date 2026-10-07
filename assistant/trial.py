"""3 lượt khách theo bản cài/SQLite local; tiếp tục tool không tính lượt mới."""
import json
import uuid
from copy import deepcopy
from .storage import dumps, now

GUEST_OWNER=':guest:'
LIMIT=3

class TrialLimitError(PermissionError):
    pass

class GuestTrial:
    def __init__(self,store):
        self.store=store
        with store.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS guest_trial_usage(
                id INTEGER PRIMARY KEY CHECK(id=1),used INTEGER NOT NULL CHECK(used>=0 AND used<=3));
                INSERT OR IGNORE INTO guest_trial_usage VALUES(1,0);
                CREATE TABLE IF NOT EXISTS guest_trial_turns(
                token TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,created TEXT NOT NULL);''')

    def remaining(self):
        with self.store.connection() as db:
            return max(0,LIMIT-db.execute('SELECT used FROM guest_trial_usage WHERE id=1').fetchone()[0])

    def consume(self,cid,state):
        if state.get('account_username')!=GUEST_OWNER:raise PermissionError('Lượt dùng thử cần hội thoại khách.')
        token=state.get('guest_trial_token')
        if not token:raise ValueError('Thiếu mã lượt dùng thử.')
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT conversation_id FROM guest_trial_turns WHERE token=?',(token,)).fetchone()
            if row:
                if row[0]!=cid:raise PermissionError('Mã lượt thuộc hội thoại khác.')
                return
            used=db.execute('SELECT used FROM guest_trial_usage WHERE id=1').fetchone()[0]
            if used>=LIMIT:raise TrialLimitError('Đăng nhập để tiếp tục trò chuyện.')
            db.execute('UPDATE guest_trial_usage SET used=used+1 WHERE id=1')
            db.execute('INSERT INTO guest_trial_turns VALUES(?,?,?)',(token,cid,now()))
            db.execute('UPDATE conversations SET state=? WHERE id=?',(dumps(state),cid))

    def start(self,agent,state,prompt,model,images=None,**kwargs):
        if self.remaining()==0:raise TrialLimitError('Đăng nhập để gửi câu hỏi tiếp theo.')
        owner=state.get('account_username')
        if owner not in (None,GUEST_OWNER):raise PermissionError('Không dùng thử trên hội thoại tài khoản khác.')
        original=deepcopy(state)
        try:
            # Agent.start xác thực đầu vào trước khi tăng bộ đếm.
            agent.start(state,prompt,model,images=images, **kwargs)
            state['account_username']=GUEST_OWNER
            state['guest_trial_token']=uuid.uuid4().hex
            self.consume(agent.cid,state)
        except Exception:
            state.clear();state.update(original);agent.save(state)
            raise

    def can_continue(self,cid,state):
        if state.get('account_username')!=GUEST_OWNER:return False
        token=state.get('guest_trial_token')
        if not token:return False
        with self.store.connection() as db:
            return db.execute('SELECT 1 FROM guest_trial_turns WHERE token=? AND conversation_id=?',(token,cid)).fetchone() is not None

    def adopt(self,username):
        if not username or username==GUEST_OWNER:raise ValueError('Cần tài khoản đăng nhập thật.')
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT id,state FROM conversations').fetchall()
            for cid,raw in rows:
                state=json.loads(raw)
                if state.get('account_username')==GUEST_OWNER:
                    state['account_username']=username
                    db.execute('UPDATE conversations SET state=? WHERE id=?',(dumps(state),cid))
