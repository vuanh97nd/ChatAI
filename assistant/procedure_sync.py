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
        changed=0;self.rejected=[];self.skipped=[];upload_error=None
        admin=self.session.get('is_system') is True or self.session.get('role')=='system' or self.owner.lower()=='admin'
        try:changed+=self.upload(admin)
        except Exception as error:
            if getattr(error,'status',None) in (401,403):raise
            upload_error=error
        changed+=self.download()
        if upload_error:raise upload_error
        return changed

    def upload(self,admin):
        changed=0
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
                    if not cleaned:
                        # An invalid local record is skipped (until it changes) instead of blocking the queue.
                        hashes[identifier]='INVALID';continue
                    record=public_record(cleaned[0]) if scope=='shared' else cleaned[0]
                    digest=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    hashes[identifier]=digest
                    if old_hash!=digest:updates.append(record)
                if updates:
                    try:self.api('put',scope=scope,records=updates)
                    except Exception as error:
                        if getattr(error,'status',None)!=400:raise
                        # One rejected record fails the whole batch: retry one by one, park the rejected ones.
                        for record in updates:
                            try:self.api('put',scope=scope,records=[record])
                            except Exception as single:
                                if getattr(single,'status',None)!=400:raise
                                hashes[record['id']]='REJECTED';self.rejected.append((record['id'],str(single)[:200]))
                with self.store.connection() as db:
                    for identifier,raw,_ in rows:
                        db.execute('INSERT OR REPLACE INTO procedure_uploads VALUES (?,?,?,?,?)',(self.server,self.owner,identifier,scope,hashes[identifier]))
                        db.execute('INSERT OR REPLACE INTO procedure_upload_sources VALUES (?,?,?,?,?)',(self.server,self.owner,identifier,scope,raw))
                changed+=len(updates)
        return changed

    def download(self):
        changed=0
        with self.store.connection() as db:
            row=db.execute('SELECT cursor FROM procedure_sync WHERE server=? AND owner=?',(self.server,self.owner)).fetchone()
        cursor=row[0] if row else 0
        shared_owner='@shared:'+hashlib.sha256(self.server.encode()).hexdigest()
        while True:
            page=self.api('list',cursor=cursor)
            rows=page.get('items',[])
            # A record this client cannot validate (e.g. newer schema) is skipped and
            # reported; stopping the cursor on it would freeze every later lesson.
            valid=[]
            for row in rows:
                record=row.get('record')
                if not isinstance(record,dict) or not isinstance(record.get('id'),str):continue
                if row.get('deleted') or len(clean_records([record]))==1:valid.append(row)
                else:self.skipped.append(record['id'])
            with self.store.connection() as db:
                for row in valid:
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
