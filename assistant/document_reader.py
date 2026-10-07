"""Read complete supported documents with honest extraction coverage."""
from io import BytesIO
from pathlib import Path
import zipfile

MAX_BYTES = 32 * 1024**2
MAX_TEXT = 4_000_000


def read_bytes(raw, name, mime=''):
    if len(raw) > MAX_BYTES:
        raise ValueError('Tài liệu vượt giới hạn 32 MiB; chưa đọc toàn văn.')
    ext = Path(name.split('?')[0]).suffix.lower()
    pages, missing = [], []
    if raw.startswith(b'PK') and ext!='.docx':
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if 'word/document.xml' in archive.namelist():ext='.docx'
        except zipfile.BadZipFile:pass
    if raw.startswith(b'%PDF') or ext == '.pdf' or 'application/pdf' in mime:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError('PDF mã hóa; cần bản có thể đọc.')
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            pages.append({'page': i, 'text': text})
            if not text.strip(): missing.append(i)
        fmt = 'pdf'
    elif ext == '.docx' or 'wordprocessingml' in mime:
        from docx import Document
        with zipfile.ZipFile(BytesIO(raw)) as z:
            if sum(x.file_size for x in z.infolist()) > 64 * 1024**2:
                raise ValueError('DOCX giải nén quá lớn.')
        doc = Document(BytesIO(raw))
        # Keep paragraphs/tables in their actual body order; Word has no reliable pages.
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        blocks = []
        for child in doc.element.body:
            if child.tag.endswith('}p'): blocks.append(Paragraph(child, doc).text)
            elif child.tag.endswith('}tbl'):
                blocks.extend(' | '.join(c.text for c in row.cells) for row in Table(child, doc).rows)
        for section in doc.sections:
            blocks.extend(p.text for p in section.header.paragraphs)
            blocks.extend(p.text for p in section.footer.paragraphs)
        pages = [{'page': None, 'text': '\n'.join(blocks)}]; fmt = 'docx'
    else:
        content = raw.decode('utf-8-sig', errors='replace')
        fmt = 'html' if 'html' in mime or ext in ('.html', '.htm') else 'text'
        if fmt == 'html':
            from html.parser import HTMLParser
            class Reader(HTMLParser):
                def __init__(self): super().__init__(); self.parts=[]; self.hidden=0; self.links=[]
                def handle_starttag(self, tag, attrs):
                    if tag in ('script','style','noscript'): self.hidden += 1
                    if tag == 'a':
                        href = dict(attrs).get('href','')
                        if href: self.links.append(href)
                def handle_endtag(self, tag):
                    if tag in ('script','style','noscript'): self.hidden=max(0,self.hidden-1)
                def handle_data(self, value):
                    if not self.hidden and value.strip(): self.parts.append(value.strip())
            parser=Reader(); parser.feed(content)
            content='\n'.join(parser.parts)
            try:
                import trafilatura
                content=trafilatura.extract(raw.decode('utf-8',errors='replace'),include_tables=True,include_comments=False) or content
            except ImportError: pass
        pages=[{'page':None,'text':content}]
    size=sum(len(p['text']) for p in pages)
    if size > MAX_TEXT: raise ValueError('Văn bản vượt 4 triệu ký tự; chưa xử lý toàn văn.')
    if not any(p['text'].strip() for p in pages): raise ValueError('Không có văn bản đọc được; bản scan cần OCR.')
    result={'text':'\n'.join(('\n[Trang %s]\n'%p['page'] if p['page'] else '')+p['text'] for p in pages),
            'pages':pages,'page_count':len(pages) if fmt=='pdf' else None,
            'missing_pages':missing,'truncated':bool(missing),'coverage':'partial' if missing else 'complete',
            'format':fmt,'full_document':fmt in ('pdf','docx','text') and not missing}
    if fmt=='html': result['links']=parser.links
    return result


def read_path(path):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>MAX_BYTES: raise ValueError('File không hợp lệ hoặc quá 32 MiB.')
    return dict(read_bytes(p.read_bytes(),p.name),file=p.name)
