"""Lưu đánh giá và bản chụp câu trả lời theo tài khoản, không tự huấn luyện."""
from .storage import now

class FeedbackStore:
    def __init__(self,store):
        self.store=store
        with store.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS answer_feedback(
                owner TEXT NOT NULL,conversation_id TEXT NOT NULL,message_index INTEGER NOT NULL,
                vote INTEGER NOT NULL,comment TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,
                model TEXT,routing TEXT,updated TEXT NOT NULL,
                PRIMARY KEY(owner,conversation_id,message_index))''')

    def put(self,owner,cid,index,vote,comment=''):
        from .storage import dumps
        if vote not in (-1,1):raise ValueError('Đánh giá phải là +1 hoặc -1.')
        state=self.store.load(cid)
        if not owner or state.get('account_username')!=owner:raise PermissionError('Hội thoại không thuộc tài khoản này.')
        messages=state['messages']
        if not 0<=index<len(messages) or messages[index]['role']!='assistant' or messages[index].get('tool_calls'):
            raise ValueError('Chỉ đánh giá câu trả lời hoàn chỉnh.')
        question=next((m['content'] for m in reversed(messages[:index]) if m['role']=='user'),'')
        with self.store.connection() as db:
            db.execute('INSERT OR REPLACE INTO answer_feedback VALUES(?,?,?,?,?,?,?,?,?,?)',
                (owner,cid,index,vote,comment[:1000],question,messages[index]['content'],state.get('model'),dumps(state.get('routing')),now()))

    def poor_answers(self,owner,limit=100):
        with self.store.connection() as db:
            rows=db.execute('SELECT question,answer,comment,model,updated FROM answer_feedback WHERE owner=? AND vote=-1 ORDER BY updated DESC LIMIT ?',
                (owner,min(100,max(1,int(limit))))).fetchall()
        return [dict(zip(('question','answer','comment','model','updated'),row)) for row in rows]
