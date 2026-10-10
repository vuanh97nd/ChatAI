"""Thư viện tài liệu: AI ghi nhớ file đã đọc và tự nhớ lại ở các lần hỏi sau.

- Lưu trên máy: %LOCALAPPDATA%/ChatAI/library/<mã tài khoản>/library.sqlite3 (không nằm trên Drive).
- Tìm kết hợp: từ khóa chính xác (SQLite FTS5, bỏ dấu) + theo nghĩa (embedding bge-m3 qua Ollama).
- Đồng bộ giữa các máy qua server Chat AI (D1): chỉ gửi chữ đã trích, nén zlib, server mã hóa.
Không gọi mạng hay model khi chưa cần; mọi lỗi đồng bộ/embedding đều không làm hỏng chat.
"""
import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
import zlib
from pathlib import Path

EMBED_MODEL = 'bge-m3'
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
PART_CHARS = 650000          # base64 mỗi phần gửi server (< 700 KB)
MAX_TEXT = __import__('sys').maxsize
CODE_PATTERN = re.compile(
    r'(?<![\w])(?:TCVN|TCCS|QCVN|TCN|TCXD|TCXDVN|ISO|IEC|EN|ASTM|AASHTO|JIS|BS|DIN|ACI|QĐ|NĐ|TT|QH)'
    r'[\s-]*\d[\w.:/-]*', re.I)


def library_root():
    base = os.environ.get('LOCALAPPDATA') or str(Path.home() / '.local' / 'share')
    return Path(base) / 'ChatAI' / 'library'


def fold(text):
    text = unicodedata.normalize('NFKD', str(text).casefold()).replace('đ', 'd')
    return ''.join(c for c in text if not unicodedata.combining(c))


def find_codes(text):
    seen = []
    for match in CODE_PATTERN.finditer(text[:200000]):
        code = re.sub(r'\s+', ' ', match.group(0)).strip(' .,:;-/')
        if 4 <= len(code) <= 60 and code.upper() not in (c.upper() for c in seen):
            seen.append(code)
        if len(seen) >= 12:
            break
    return seen


def compact_code(code):
    return re.sub(r'\W', '', fold(code))


def make_units(item):
    """Đưa kết quả đọc file về danh sách đơn vị {location,text}."""
    units = [u for u in (item.get('units') or []) if str(u.get('text', '')).strip()]
    if units:
        return [{'location': str(u.get('location') or 'nội dung'), 'text': str(u['text'])} for u in units]
    text = str(item.get('text') or '')
    parts = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    return [{'location': f'đoạn {i}', 'text': p} for i, p in enumerate(parts, 1)]


def extract_full(path):
    """Đọc toàn văn cho định dạng mà màn hình chat chỉ đọc một phần (PPTX, XLSX)."""
    p = Path(path)
    ext = p.suffix.lower()
    units = []
    if ext == '.pptx':
        from pptx import Presentation
        for index, slide in enumerate(Presentation(p).slides, 1):
            text = '\n'.join(shape.text for shape in slide.shapes if getattr(shape, 'has_text_frame', False))
            if text.strip():
                units.append({'location': f'slide {index}', 'text': text})
    elif ext in ('.xlsx', '.xlsm'):
        import pandas as pd
        book = pd.ExcelFile(p)
        try:
            for name in book.sheet_names[:20]:
                frame = book.parse(name, nrows=5000)
                csv = frame.to_csv(index=False)
                for start in range(0, min(len(csv), MAX_TEXT), 4000):
                    units.append({'location': f'sheet {name}', 'text': csv[start:start + 4000]})
        finally:
            book.close()
    return units


def split_chunks(units):
    chunks = []
    for unit in units:
        text = re.sub(r'[ \t]+', ' ', unit['text']).strip()
        if not text:
            continue
        step = CHUNK_CHARS - CHUNK_OVERLAP
        for start in range(0, len(text), step):
            piece = text[start:start + CHUNK_CHARS]
            if len(piece.strip()) < 20 and start:
                continue
            chunks.append({'location': unit['location'], 'text': piece})
            if start + CHUNK_CHARS >= len(text):
                break
    return chunks


def summary_of(title, units, codes):
    body = ' '.join(re.sub(r'\s+', ' ', u['text']) for u in units[:12])
    head = body[:700].strip()
    pages = [u['location'] for u in units if u['location'].startswith('trang ')]
    lines = [f'Tên: {title}']
    if codes:
        lines.append('Số hiệu: ' + ', '.join(codes[:6]))
    if pages:
        lines.append(f'Số trang có chữ: {len(pages)}')
    lines.append('Mở đầu: ' + head + ('…' if len(body) > 700 else ''))
    return '\n'.join(lines)


class Library:
    def __init__(self, owner, client=None):
        if not owner:
            raise ValueError('Thư viện cần tên tài khoản.')
        self.owner = owner
        self.client = client
        folder = library_root() / hashlib.sha256(owner.encode('utf-8')).hexdigest()[:16]
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / 'library.sqlite3'
        self.lock = threading.RLock()
        self.fts = True
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS docs(id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL DEFAULT '',
                    codes TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '', pages INTEGER NOT NULL DEFAULT 0,
                    chars INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0,
                    deleted INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS texts(id TEXT PRIMARY KEY, data BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks(rowid INTEGER PRIMARY KEY, doc TEXT NOT NULL, idx INTEGER NOT NULL,
                    location TEXT NOT NULL, text TEXT NOT NULL, vector BLOB);
                CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc);
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
            try:
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, location, content='chunks', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2')")
            except sqlite3.OperationalError:
                self.fts = False

    def db(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute('PRAGMA journal_mode=WAL')
        return _Closing(connection)

    # ---------- ghi nhớ ----------
    def remember(self, item, path=None, synced=False, ident=None):
        """Ghi nhớ một tài liệu đã đọc. Trả về id, hoặc None nếu không có chữ."""
        units = make_units(item)
        if path and Path(path).suffix.lower() in ('.pptx', '.xlsx', '.xlsm'):
            try:
                full = extract_full(path)
                if full:
                    units = full
            except Exception:
                pass
        text = '\n\n'.join('[' + u['location'] + ']\n' + u['text'] for u in units)[:MAX_TEXT]
        if len(text.strip()) < 40 or text.startswith('Tệp nhị phân đã đính kèm'):
            return None
        ident = ident or hashlib.sha256(re.sub(r'\s+', ' ', text).strip().encode('utf-8')).hexdigest()
        filename = str(item.get('file') or (Path(path).name if path else 'tài liệu'))
        title = (str(item.get('title') or '').strip() or Path(filename).stem)[:300]
        codes = find_codes(text)
        with self.lock, self.db() as db:
            row = db.execute('SELECT deleted FROM docs WHERE id=?', (ident,)).fetchone()
            if row and not row[0]:
                return ident
            if row:
                db.execute('DELETE FROM docs WHERE id=?', (ident,))
                self._drop_chunks(db, ident)
            pages = sum(1 for u in units if u['location'].startswith('trang '))
            db.execute('INSERT INTO docs(id,title,filename,codes,summary,pages,chars,created,synced,deleted) VALUES(?,?,?,?,?,?,?,?,?,0)',
                       (ident, title, filename, ', '.join(codes), summary_of(title, units, codes), pages, len(text),
                        time.strftime('%Y-%m-%d %H:%M'), 1 if synced else 0))
            db.execute('INSERT OR REPLACE INTO texts(id,data) VALUES(?,?)', (ident, zlib.compress(text.encode('utf-8'), 9)))
            for index, chunk in enumerate(split_chunks(units)):
                cursor = db.execute('INSERT INTO chunks(doc,idx,location,text,vector) VALUES(?,?,?,?,NULL)',
                                    (ident, index, chunk['location'], chunk['text']))
                if self.fts:
                    db.execute('INSERT INTO chunks_fts(rowid,text,location) VALUES(?,?,?)',
                               (cursor.lastrowid, chunk['text'], chunk['location']))
        return ident

    def _drop_chunks(self, db, ident):
        if self.fts:
            for rowid, text, location in db.execute('SELECT rowid,text,location FROM chunks WHERE doc=?', (ident,)).fetchall():
                db.execute("INSERT INTO chunks_fts(chunks_fts,rowid,text,location) VALUES('delete',?,?,?)", (rowid, text, location))
        db.execute('DELETE FROM chunks WHERE doc=?', (ident,))

    def forget(self, ident):
        with self.lock, self.db() as db:
            self._drop_chunks(db, ident)
            db.execute('DELETE FROM texts WHERE id=?', (ident,))
            db.execute('UPDATE docs SET deleted=1, synced=0, summary=\'\' WHERE id=?', (ident,))

    def documents(self):
        with self.db() as db:
            rows = db.execute('SELECT id,title,filename,codes,summary,pages,chars,created,synced FROM docs WHERE deleted=0 ORDER BY created DESC').fetchall()
        keys = ('id', 'title', 'filename', 'codes', 'summary', 'pages', 'chars', 'created', 'synced')
        return [dict(zip(keys, row)) for row in rows]

    def full_text(self, ident):
        with self.db() as db:
            row = db.execute('SELECT data FROM texts WHERE id=?', (ident,)).fetchone()
        return zlib.decompress(row[0]).decode('utf-8') if row else ''

    # ---------- embedding ----------
    def embed_pending(self, limit=256, batch=16):
        """Tạo vector cho các đoạn chưa có (chạy nền, CPU). Trả về số đoạn đã xử lý."""
        if self.client is None:
            return 0
        from .memory import embed
        done = 0
        while done < limit:
            with self.db() as db:
                rows = db.execute('SELECT rowid,text FROM chunks WHERE vector IS NULL LIMIT ?', (batch,)).fetchall()
            if not rows:
                break
            vectors = embed(self.client, [text[:2000] for _, text in rows])
            packed = [(_pack(v), rowid) for (rowid, _), v in zip(rows, vectors)]
            with self.lock, self.db() as db:
                db.executemany('UPDATE chunks SET vector=? WHERE rowid=?', packed)
            done += len(rows)
        return done

    # ---------- tìm lại ----------
    def search(self, question, limit=4, semantic=True):
        """Tìm đoạn liên quan. Trả về danh sách {'source','chunk','text','score','doc'}."""
        question = (question or '').strip()
        if len(question) < 3:
            return []
        scores = {}
        texts = {}
        flags = {}
        # 1) Số hiệu tài liệu khớp chính xác: ưu tiên cao nhất.
        codes = [compact_code(c) for c in find_codes(question)]
        with self.db() as db:
            docs = db.execute('SELECT id,title,codes FROM docs WHERE deleted=0').fetchall()
            titles = {ident: title for ident, title, _ in docs}
            code_docs = {ident for ident, _, doc_codes in docs
                         if codes and any(c and c in compact_code(doc_codes) for c in codes)}
            # 2) Từ khóa (FTS5, bỏ dấu).
            words = [w for w in re.findall(r'\w+', question) if len(w) >= 2][:12]
            if words and self.fts:
                query = ' OR '.join('"' + w.replace('"', '') + '"' for w in words)
                try:
                    rows = db.execute('SELECT c.rowid,c.doc,c.location,c.text,bm25(chunks_fts) FROM chunks_fts '
                                      'JOIN chunks c ON c.rowid=chunks_fts.rowid WHERE chunks_fts MATCH ? '
                                      'ORDER BY bm25(chunks_fts) LIMIT 30', (query,)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                for rank, (rowid, doc, location, text, _) in enumerate(rows):
                    scores[rowid] = scores.get(rowid, 0) + 1.0 / (10 + rank)
                    texts[rowid] = (doc, location, text)
                    flags.setdefault(rowid, {})['keyword'] = True
            # 3) Theo nghĩa (vector).
            vector_rows = []
            if semantic and self.client is not None:
                try:
                    from .memory import embed
                    query_vector = embed(self.client, [question[:1600]])[0]
                    vector_rows = _vector_rank(db, query_vector, 30)
                except Exception:
                    vector_rows = []
            for rank, (rowid, doc, location, text, similarity) in enumerate(vector_rows):
                if similarity < 0.5:
                    continue
                scores[rowid] = scores.get(rowid, 0) + 1.0 / (10 + rank) + max(0, similarity - 0.5)
                texts[rowid] = (doc, location, text)
                flags.setdefault(rowid, {})['similarity'] = round(similarity, 3)
            if code_docs:
                rows = db.execute('SELECT rowid,doc,location,text FROM chunks WHERE doc IN (%s) ORDER BY idx LIMIT 40'
                                  % ','.join('?' * len(code_docs)), tuple(code_docs)).fetchall()
                for rowid, doc, location, text in rows:
                    scores[rowid] = scores.get(rowid, 0) + 0.15
                    texts[rowid] = (doc, location, text)
                    flags.setdefault(rowid, {})['code'] = True
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results = []
        for rowid, score in ranked[:limit]:
            doc, location, text = texts[rowid]
            flag = flags.get(rowid, {})
            results.append({'source': titles.get(doc, 'Tài liệu'), 'chunk': location, 'text': text,
                            'score': round(score, 3), 'doc': doc, 'code': flag.get('code', False),
                            'keyword': flag.get('keyword', False), 'similarity': flag.get('similarity', 0.0)})
        return results

    # ---------- đồng bộ ----------
    def sync(self, session, progress=None):
        """Đẩy tài liệu mới lên server và tải tài liệu từ máy khác về. Trả về thống kê."""
        from .accounts import request_account
        if not session or not session.get('endpoint'):
            return {'pushed': 0, 'pulled': 0, 'deleted': 0, 'note': 'Chưa đăng nhập server.'}
        auth = {'username': session['username'], 'key': session['key']}
        endpoint = session['endpoint']
        stats = {'pushed': 0, 'pulled': 0, 'deleted': 0}
        with self.db() as db:
            pending = db.execute('SELECT id,title,filename,codes,summary,pages,chars,deleted FROM docs WHERE synced=0').fetchall()
        for ident, title, filename, codes, summary, pages, chars, deleted in pending:
            if deleted:
                request_account(endpoint, '/api/library/delete', {**auth, 'id': ident}, timeout=30)
                stats['deleted'] += 1
            else:
                blob = base64.b64encode(zlib.compress(self.full_text(ident).encode('utf-8'), 9)).decode('ascii')
                parts = [blob[i:i + PART_CHARS] for i in range(0, len(blob), PART_CHARS)] or ['']
                for number, data in enumerate(parts):
                    if progress:
                        progress(f'Đang đồng bộ thư viện: {title[:40]} ({number + 1}/{len(parts)})')
                    result = request_account(endpoint, '/api/library/put', {
                        **auth, 'id': ident, 'part': number, 'parts': len(parts), 'data': data,
                        'total_bytes': len(blob), 'title': title, 'filename': filename, 'codes': codes,
                        'summary': summary, 'pages': pages, 'chars': chars}, timeout=60)
                    if result.get('exists'):
                        break
                stats['pushed'] += 1
            with self.lock, self.db() as db:
                db.execute('UPDATE docs SET synced=1 WHERE id=?', (ident,))
        with self.db() as db:
            row = db.execute("SELECT value FROM meta WHERE key='last_sync'").fetchone()
        since = row[0] if row else ''
        listing = request_account(endpoint, '/api/library/list', {**auth, 'since': since}, timeout=30)
        newest = since
        for remote in listing.get('items', []):
            newest = max(newest, remote.get('updated_at') or '')
            ident = remote.get('id')
            with self.db() as db:
                local = db.execute('SELECT deleted FROM docs WHERE id=?', (ident,)).fetchone()
            if remote.get('deleted_at'):
                if local and not local[0]:
                    self.forget(ident)
                    with self.db() as db:
                        db.execute('UPDATE docs SET synced=1 WHERE id=?', (ident,))
                    stats['deleted'] += 1
                continue
            if local is not None or not remote.get('complete'):
                continue
            pieces = []
            for number in range(int(remote.get('parts') or 0)):
                if progress:
                    progress(f'Đang tải tài liệu từ máy khác: {remote.get("title", "")[:40]}')
                pieces.append(request_account(endpoint, '/api/library/get', {**auth, 'id': ident, 'part': number}, timeout=60)['data'])
            text = zlib.decompress(base64.b64decode(''.join(pieces))).decode('utf-8')
            units = []
            for block in re.split(r'\n\n(?=\[)', text):
                match = re.match(r'\[([^\]]{1,80})\]\n', block)
                units.append({'location': match.group(1) if match else 'nội dung',
                              'text': block[match.end():] if match else block})
            self.remember({'units': units, 'file': remote.get('filename'), 'title': remote.get('title')}, synced=True, ident=ident)
            stats['pulled'] += 1
        if newest and newest != since:
            with self.lock, self.db() as db:
                db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('last_sync',?)", (newest,))
        stats['usage'] = listing.get('usage')
        return stats


class _Closing:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
        return False


def _pack(vector):
    try:
        import numpy as np
        return np.asarray(vector, dtype='float32').tobytes()
    except ImportError:
        from array import array
        return array('f', vector).tobytes()


def _vector_rank(db, query_vector, limit):
    rows = db.execute('SELECT rowid,doc,location,text,vector FROM chunks WHERE vector IS NOT NULL').fetchall()
    if not rows:
        return []
    try:
        import numpy as np
        query = np.asarray(query_vector, dtype='float32')
        matrix = np.frombuffer(b''.join(r[4] for r in rows), dtype='float32').reshape(len(rows), -1)
        if matrix.shape[1] != query.shape[0]:
            return []
        norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1)
        similarity = matrix @ query / np.where(norms == 0, 1, norms)
        order = np.argsort(-similarity)[:limit]
        return [(rows[i][0], rows[i][1], rows[i][2], rows[i][3], float(similarity[i])) for i in order]
    except ImportError:
        from array import array
        import math
        qn = math.sqrt(sum(x * x for x in query_vector)) or 1
        scored = []
        for rowid, doc, location, text, blob in rows:
            vec = array('f');vec.frombytes(blob)
            if len(vec) != len(query_vector):
                continue
            vn = math.sqrt(sum(x * x for x in vec)) or 1
            scored.append((rowid, doc, location, text, sum(a * b for a, b in zip(vec, query_vector)) / (qn * vn)))
        scored.sort(key=lambda r: r[4], reverse=True)
        return scored[:limit]
