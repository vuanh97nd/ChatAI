"""Paginated lesson synchronization independent of chat history size or running tasks."""
import hashlib
import json
from .procedure_memory import ProcedureMemory,clean_records,public_record


class ProcedureSync:
    def __init__(self,store,session,request=None):
        self.store=store;self.session=dict(session);self.owner=session['username'];self.server=session['endpoint'].rstrip('/')
        if request is None:
            from .accounts import request_account
            request=lambda path,body:request_account(self.server,path,body,timeout=20)
        self.request=request
        self.memory=ProcedureMemory(store)

    def api(self,action,**body):
        return self.request('/api/lessons/'+action,{'username':self.owner,'key':self.session['key'],**body})

    def cycle(self):
        with self.store.connection() as db:
            db.execute('INSERT INTO procedure_accounts VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET server=excluded.server',(self.owner,self.server))
        changed=0
        admin=self.session.get('is_system') is True or self.session.get('role')=='system' or self.owner.lower()=='admin'
        for scope in ('private','shared'):
            if scope=='shared' and not admin:continue
            while True:
                with self.store.connection() as db:
                    query="""SELECT p.id,p.data,u.hash FROM procedure_memory p
                        LEFT JOIN procedure_upload_sources s ON s.server=? AND s.owner=p.owner AND s.id=p.id AND s.scope=?
                        LEFT JOIN procedure_uploads u ON u.server=? AND u.owner=p.owner AND u.id=p.id AND u.scope=?
                        WHERE p.owner=? AND (s.snapshot IS NULL OR s.snapshot<>p.data)"""
                    if scope=='shared':query+=" AND json_extract(p.data,'$.training')=1"
                    rows=db.execute(query+' ORDER BY p.id LIMIT 10',(self.server,scope,self.server,scope,self.owner)).fetchall()
                if not rows:break
                updates=[];hashes={}
                for identifier,raw,old_hash in rows:
                    cleaned=clean_records([json.loads(raw)])
                    if not cleaned:raise ValueError('Bài học trên máy không hợp lệ.')
                    record=public_record(cleaned[0]) if scope=='shared' else cleaned[0]
                    digest=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    hashes[identifier]=digest
                    if old_hash!=digest:updates.append(record)
                if updates:self.api('put',scope=scope,records=updates)
                with self.store.connection() as db:
                    for identifier,raw,_ in rows:
                        db.execute('INSERT OR REPLACE INTO procedure_uploads VALUES (?,?,?,?,?)',(self.server,self.owner,identifier,scope,hashes[identifier]))
                        db.execute('INSERT OR REPLACE INTO procedure_upload_sources VALUES (?,?,?,?,?)',(self.server,self.owner,identifier,scope,raw))
                changed+=len(updates)
        with self.store.connection() as db:
            row=db.execute('SELECT cursor FROM procedure_sync WHERE server=? AND owner=?',(self.server,self.owner)).fetchone()
        cursor=row[0] if row else 0
        shared_owner='@shared:'+hashlib.sha256(self.server.encode()).hexdigest()
        while True:
            page=self.api('list',cursor=cursor)
            rows=page.get('items',[])
            # Do not advance a cursor unless every row was validated and stored.
            for row in rows:
                cleaned=clean_records([row.get('record')])
                if len(cleaned)!=1:raise ValueError('Server trả bài học không hợp lệ; chưa cập nhật cursor.')
            with self.store.connection() as db:
                for row in rows:
                    target=shared_owner if row['scope']=='shared' else self.owner
                    if row.get('deleted'):
                        db.execute('DELETE FROM procedure_memory WHERE owner=? AND id=?',(target,row['record']['id']))
                    else:self.memory.import_records(target,[row['record']],db=db)
                next_cursor=page['cursor']
                if not isinstance(next_cursor,int) or next_cursor<cursor:raise ValueError('Cursor bộ nhớ không hợp lệ.')
                db.execute('INSERT OR REPLACE INTO procedure_sync VALUES (?,?,?)',(self.server,self.owner,next_cursor))
            changed+=len(rows);cursor=next_cursor
            if not page.get('has_more'):break
        return changed
