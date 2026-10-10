"""Account-scoped text history synchronization; local SQLite remains the offline cache."""
import hashlib
import json
import uuid
from .storage import dumps, now
from .document_memory import clean_records
from .procedure_memory import clean_records as clean_procedures,clean_progress
from .plaxis_confirmation import active_problem


def dialogue(state):
    return {'messages':[{'role':m['role'],'content':m.get('content',''),**({'tool_name':str(m.get('tool_name') or 'tool')[:100]} if m['role']=='tool' else {})}
                        for m in state.get('messages',[]) if m.get('role') in ('user','assistant','tool')
                        and isinstance(m.get('content',''),str)],
            'custom_title':str(state.get('custom_title') or '')[:120], 'model':state.get('model')[:150] if isinstance(state.get('model'),str) else None,
            'online_automation':state.get('online_automation') is True,
            'document_memory':clean_records(state.get('document_memory',[])),
            'procedure_memory':clean_procedures(state.get('procedure_memory',[])),
            'procedure_progress':clean_progress(state.get('procedure_progress',{})),
            'procedure_environment':str(state.get('procedure_environment') or 'unknown')[:160],
            'plaxis_active_problem':active_problem(state)}


def fingerprint(state):
    return hashlib.sha256(dumps(dialogue(state)).encode()).hexdigest()


class HistorySync:
    def __init__(self,store,session,request=None):
        self.store=store;self.session=dict(session)
        self.owner=session['username'];self.server=session['endpoint'].rstrip('/')
        if request is None:
            from .accounts import request_account
            request=lambda path,body:request_account(self.server,path,body,timeout=20)
        self.request=request

    def api(self,action,**body):
        return self.request('/api/conversations/sync/'+action,
                            {'username':self.owner,'key':self.session['key'],**body})

    def baseline(self,cid):
        with self.store.connection() as db:
            row=db.execute('SELECT revision,hash FROM history_sync WHERE server=? AND owner=? AND id=?',
                           (self.server,self.owner,cid)).fetchone()
        return row or (0,None)

    def mark(self,cid,revision,hash_value):
        with self.store.connection() as db:
            db.execute('INSERT OR REPLACE INTO history_sync VALUES (?,?,?,?,?)',
                       (self.server,self.owner,cid,revision,hash_value))

    def import_remote(self,cid,remote,expected):
        """Keep local attachments; never restore a pending tool or running action."""
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state FROM conversations WHERE id=?',(cid,)).fetchone()
            current=json.loads(row[0]) if row else None
            if current and current.get('account_username')!=self.owner:return False
            if current and (current.get('running') or current.get('pending') or current.get('queue')):return False
            if (fingerprint(current) if current else None)!=expected:return False
            state=remote['state']
            from .document_memory import DocumentMemory
            DocumentMemory(self.store).import_records(self.owner,state.get('document_memory',[]),db=db)
            from .procedure_memory import ProcedureMemory
            ProcedureMemory(self.store).import_records(self.owner,state.get('procedure_memory',[]),db=db)
            state['procedure_memory_version']=1
            state['document_memory_version']=1
            if remote['deleted']:
                if current:
                    db.execute('INSERT INTO audit(at,conversation_id,action,details) VALUES (?,?,?,?)',
                               (now(),cid,'cloud_history_archived',dumps({'state':current})))
                    db.execute('DELETE FROM conversations WHERE id=?',(cid,))
                db.execute('DELETE FROM history_deletions WHERE id=?',(cid,))
            else:
                state={**state,'account_username':self.owner,'queue':[],'pending':None,
                       'running':False,'rounds':0}
                # Attachments stay on this device, and match their original message only.
                if current:
                    old=current.get('messages',[])
                    for i,m in enumerate(state['messages']):
                        if i<len(old) and m=={k:old[i].get(k,'') for k in ('role','content')}:
                            for key in ('images','documents'):
                                if key in old[i]:m[key]=old[i][key]
                title=state.get('custom_title') or next((m['content'][:60] for m in state['messages'] if m['role']=='user'),'Cuộc trò chuyện mới')
                db.execute('INSERT OR REPLACE INTO conversations VALUES (?,?,?,?)',(cid,title,remote.get('updated_at') or now(),dumps(state)))
                db.execute('DELETE FROM history_deletions WHERE id=?',(cid,))
            db.execute('INSERT OR REPLACE INTO history_sync VALUES (?,?,?,?,?)',
                       (self.server,self.owner,cid,remote['revision'],'DELETED' if remote['deleted'] else fingerprint(state)))
        return True

    def cycle(self):
        remote={};offset=0
        while True:
            page=self.api('list',offset=offset)
            remote.update((r['id'],r) for r in page['items'])
            offset=page.get('next_offset')
            if offset is None:break
        with self.store.connection() as db:
            rows=db.execute("SELECT id,state FROM conversations WHERE json_extract(state,'$.account_username')=?",(self.owner,)).fetchall()
            deletions=dict(db.execute('SELECT id,owner FROM history_deletions WHERE owner=?',(self.owner,)).fetchall())
        local={cid:json.loads(raw) for cid,raw in rows}
        changed=False;failures=[]
        for cid in sorted(set(local)|set(deletions)|set(remote)):
            # One oversized or rejected conversation must not block every later one.
            try:changed=self.sync_one(cid,local.get(cid),cid in deletions,remote.get(cid)) or changed
            except Exception as error:
                from .accounts import AccountAPIError
                if isinstance(error,AccountAPIError) and getattr(error,'status',None) in (401,403):raise
                if not isinstance(error,AccountAPIError) and not isinstance(error,(ValueError,KeyError,TypeError)):raise
                failures.append((cid,str(error)[:200]))
        self.failures=failures
        return changed

    def sync_one(self,cid,state,deleted,item):
        # The desktop only syncs while idle, so a stored running/pending flag is a
        # crash leftover or an approval wait: back up its dialogue, never overwrite it.
        if state and not state.get('messages'):return False
        revision,base_hash=self.baseline(cid)
        local_hash='DELETED' if deleted else fingerprint(state) if state else None
        if item and item['revision']!=revision:
            fetched=self.api('get',conversation_id=cid)
            remote_hash='DELETED' if fetched['deleted'] else fingerprint(fetched['state'])
            if local_hash==remote_hash:
                self.mark(cid,item['revision'],remote_hash);self.forget_deletion(cid,deleted)
                return False
            busy=state and (state.get('running') or state.get('pending') or state.get('queue'))
            if busy:return False
            if local_hash not in (None,base_hash) and state:
                # Concurrent edits: preserve the local branch instead of replacing it.
                copy=dict(state);copy['custom_title']=(copy.get('custom_title') or next((m['content'][:50] for m in copy['messages'] if m['role']=='user'),'Hội thoại'))+' (bản trên máy)'
                self.store.save(uuid.uuid4().hex,copy)
            if deleted:
                # A confirmed local deletion remains pending against the latest revision.
                revision=item['revision']
            else:
                return self.import_remote(cid,fetched,local_hash if state else None)
        if local_hash is not None and local_hash!=base_hash:
            if deleted and not item and revision==0:
                # Never uploaded: nothing to delete on the server.
                self.forget_deletion(cid,True);return False
            result=self.api('put',conversation_id=cid,revision=revision,deleted=deleted,
                            state=dialogue(state or {'messages':[]}))
            self.mark(cid,result['revision'],local_hash)
            self.forget_deletion(cid,deleted)
        return False

    def forget_deletion(self,cid,deleted):
        if not deleted:return
        with self.store.connection() as db:
            db.execute('DELETE FROM history_deletions WHERE id=? AND owner=?',(cid,self.owner))
