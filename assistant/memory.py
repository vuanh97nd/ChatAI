"""Ký ức SQLite theo tài khoản; embedding CPU tùy module, dự phòng từ khóa."""
import hashlib
import json
import math
import re
from .storage import now

EMBED_MODEL='bge-m3'


def explicit_memory_text(question):
    match=re.match(r'^\s*(?:hãy\s+)?(?:ghi nhớ|nhớ rằng|lưu vào bộ nhớ)\s*[:,-]?\s*(.+)$',question,re.I|re.S)
    return match[1] if match else None

def tokens(text):
    stop={'tôi','của','bạn','là','và','có','cho','về','một','các','để','trong','hãy','nhớ','ghi','rằng','thì','này','đó'}
    return set(re.findall(r'\w+',text.casefold()))-stop


def cosine(a,b):
    if len(a)!=len(b) or not a:return -1
    denominator=math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
    return sum(x*y for x,y in zip(a,b))/denominator if denominator else -1


def embed(client,texts):
    result=client.embed(model=EMBED_MODEL,input=texts,
        options={'num_gpu':0,'num_ctx':2048},keep_alive='2m',truncate=False)
    vectors=result['embeddings'] if isinstance(result,dict) else result.embeddings
    if len(vectors)!=len(texts) or any(not v or any(not math.isfinite(x) for x in v) for v in vectors):
        raise ValueError('Embedding không hợp lệ.')
    return vectors


class PersonalMemory:
    def __init__(self,store,client,owner,embedding_enabled=False):
        if not owner:raise ValueError('Bộ nhớ cần tài khoản đăng nhập.')
        self.store,self.client,self.owner,self.embedding_enabled=store,client,owner,embedding_enabled
        with store.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS personal_memory(
                owner TEXT NOT NULL,id TEXT NOT NULL,title TEXT NOT NULL,text TEXT NOT NULL,
                vector TEXT,embedding_model TEXT,updated TEXT NOT NULL,
                PRIMARY KEY(owner,id))''')

    def put(self,text,title='Ghi nhớ',identifier=None):
        text=text.strip()[:1200]
        if not text:return None
        if re.search(r'mật khẩu|password|api[_ -]?key|secret|token\s*[:=]',text,re.I):
            raise ValueError('Không lưu mật khẩu hoặc khóa truy cập vào ký ức.')
        ident=identifier or hashlib.sha256(text.encode()).hexdigest()[:24]
        with self.store.connection() as db:
            existing=db.execute('SELECT text,vector,embedding_model,title FROM personal_memory WHERE owner=? AND id=?',(self.owner,ident)).fetchone()
            if existing and existing[0]==text and existing[3]==title[:120]:return ident
            # Durable save first. search() builds missing embeddings lazily.
            vector,model=(existing[1],existing[2]) if existing and existing[0]==text else (None,None)
            db.execute('INSERT OR REPLACE INTO personal_memory VALUES(?,?,?,?,?,?,?)',
                (self.owner,ident,title[:120],text,vector,model,now()))
        return ident

    def sync_server(self,items):
        # Server vẫn là nguồn chuẩn cho bản sao có tiền tố server:.
        ids=set()
        enabled=self.embedding_enabled
        self.embedding_enabled=False
        try:
            for item in items[:100]:
                ident='server:'+str(item['id']);ids.add(ident)
                try:self.put(item['text'],item.get('title','Bộ nhớ server'),ident)
                except ValueError:continue
        finally:
            self.embedding_enabled=enabled
        with self.store.connection() as db:
            rows=db.execute("SELECT id FROM personal_memory WHERE owner=? AND id LIKE 'server:%'",(self.owner,)).fetchall()
            for (ident,) in rows:
                if ident not in ids:db.execute('DELETE FROM personal_memory WHERE owner=? AND id=?',(self.owner,ident))

    def capture_explicit(self,question):
        text=explicit_memory_text(question)
        return self.put(text, 'Người dùng yêu cầu ghi nhớ') if text else None

    def search(self,question,limit=4):
        with self.store.connection() as db:
            rows=db.execute('SELECT id,title,text,vector,embedding_model FROM personal_memory WHERE owner=? ORDER BY updated DESC LIMIT 200',(self.owner,)).fetchall()
        if not rows:return []
        query_vector=None
        if self.embedding_enabled:
            missing=[row for row in rows if not row[3]][:8]
            try:
                vectors=embed(self.client,[question[:1600]]+[row[2] for row in missing])
                query_vector=vectors[0]
                replacements={row[0]:json.dumps(vector) for row,vector in zip(missing,vectors[1:])}
                with self.store.connection() as db:
                    for ident,vector in replacements.items():
                        db.execute('UPDATE personal_memory SET vector=?,embedding_model=? WHERE owner=? AND id=?',(vector,EMBED_MODEL,self.owner,ident))
                rows=[(ident,title,text,replacements.get(ident,vector),EMBED_MODEL if ident in replacements else model)
                      for ident,title,text,vector,model in rows]
            except Exception:pass
        query_tokens=tokens(question);ranked=[]
        for ident,title,text,vector,model in rows:
            common=query_tokens&tokens(text)
            lexical=len(common)/max(1,len(query_tokens))
            semantic=cosine(query_vector,json.loads(vector)) if query_vector and vector and model==EMBED_MODEL else -1
            if lexical==0 and semantic<.4:continue
            ranked.append((max(lexical,semantic),{'id':ident,'title':title,'text':text[:700]}))
        ranked.sort(key=lambda item:item[0],reverse=True)
        return [item for _,item in ranked[:limit]]

    def list_local(self):
        with self.store.connection() as db:
            rows=db.execute("SELECT id,title,text FROM personal_memory WHERE owner=? AND id NOT LIKE 'server:%' ORDER BY updated DESC LIMIT 200",(self.owner,)).fetchall()
        return [{'id':'local:'+ident,'title':title,'text':text,'location':'local'} for ident,title,text in rows]

    def delete(self,identifier):
        with self.store.connection() as db:
            db.execute('DELETE FROM personal_memory WHERE owner=? AND id=?',(self.owner,identifier))
