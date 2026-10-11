"""Bounded local cache. Entries are evidence/data, never execution permissions."""
import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


def cache_path():
    # Windows cache survives moving/upgrading the application folder.
    base = Path(os.environ['LOCALAPPDATA']) / 'ChatAI' if os.name == 'nt' and os.environ.get('LOCALAPPDATA') else Path(__file__).resolve().parents[1] / 'data'
    return base / 'cache' / 'memory.sqlite3'


def account_scope(owner, server=''):
    return hashlib.sha256(json.dumps([server.rstrip('/'), owner or 'guest'], ensure_ascii=False).encode()).hexdigest()


def key_for(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class RuntimeCache:
    def __init__(self, path=None, clock=time.time, max_entries=512, max_bytes=32*1024**2):
        self.path = Path(path) if path is not None else cache_path()
        self.clock, self.max_entries, self.max_bytes = clock, max_entries, max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS cache(scope TEXT, kind TEXT, key TEXT, data TEXT, expires REAL, accessed REAL, bytes INTEGER, PRIMARY KEY(scope,kind,key))')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=5)
        try:
            with db: yield db
        finally: db.close()

    def get(self, scope, kind, key):
        with self.connection() as db:
            row = db.execute('SELECT data,expires FROM cache WHERE scope=? AND kind=? AND key=?', (scope,kind,key)).fetchone()
            if row is None: return None
            if row[1] <= self.clock():
                db.execute('DELETE FROM cache WHERE scope=? AND kind=? AND key=?', (scope,kind,key))
                return None
            db.execute('UPDATE cache SET accessed=? WHERE scope=? AND kind=? AND key=?', (self.clock(),scope,kind,key))
            try: return json.loads(row[0])
            except ValueError:
                db.execute('DELETE FROM cache WHERE scope=? AND kind=? AND key=?', (scope,kind,key))
                return None

    def put(self, scope, kind, key, value, ttl=86400):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False)
        size = len(data.encode())
        if size > min(2*1024**2,self.max_bytes) or ttl <= 0: return False
        now = self.clock()
        with self.connection() as db:
            db.execute('DELETE FROM cache WHERE expires<=?',(now,))
            db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?,?)',(scope,kind,key,data,now+ttl,now,size))
            # Evict least recently used entries across all accounts to bound disk usage.
            rows=db.execute('SELECT scope,kind,key,bytes FROM cache ORDER BY accessed DESC,rowid DESC').fetchall()
            used=0
            for index,row in enumerate(rows):
                used+=row[3]
                if index>=self.max_entries or used>self.max_bytes:
                    db.execute('DELETE FROM cache WHERE scope=? AND kind=? AND key=?',row[:3])
        return True

    def clear(self, scope=None):
        with self.connection() as db:
            if scope is None: db.execute('DELETE FROM cache')
            else: db.execute('DELETE FROM cache WHERE scope=?',(scope,))


def file_stamp(path):
    p=Path(path);s=p.stat()
    return [str(p.resolve()),s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def implementation_key(names):
    """Changing reader/calculation code invalidates persisted results after upgrade."""
    root=Path(__file__).parent
    from importlib.metadata import version,PackageNotFoundError
    libraries=[]
    for package in ('openpyxl','python-docx','python-pptx','pypdf','pypdfium2'):
        try:libraries.append([package,version(package)])
        except PackageNotFoundError:libraries.append([package,None])
    return key_for([[hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names],libraries])


def optional_cache():
    try: return RuntimeCache()
    except (OSError,sqlite3.Error): return None


def safe_get(cache,*args):
    try: return cache.get(*args) if cache else None
    except (OSError,sqlite3.Error,ValueError): return None


def safe_put(cache,*args,**kwargs):
    try: return cache.put(*args,**kwargs) if cache else False
    except (OSError,sqlite3.Error,TypeError,ValueError): return False


def cached_calculate(arguments,cache,scope):
    from .calculator import calculate
    if arguments.get('operation') not in ('expression','statistics','convert','date_difference'):
        return calculate(**arguments)
    key=key_for([arguments,implementation_key(('calculator.py',))])
    result=safe_get(cache,scope,'calculation',key)
    if isinstance(result,dict) and result.get('ok') is True:return dict(result,cached=True)
    result=calculate(**arguments)
    if result.get('ok') is True:safe_put(cache,scope,'calculation',key,result)
    return result
