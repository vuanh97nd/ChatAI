"""Code artifacts: no execution; file writes reuse whitelist/backup/audit tools."""
from dataclasses import dataclass
import hashlib
import re
from pathlib import Path
from .files import FileTools, TEXT_SUFFIXES

CODE_SUFFIXES = {'.py','.pyw','.js','.ts','.tsx','.jsx','.html','.css','.json','.yaml','.yml',
                '.toml','.ini','.cfg','.xml','.sql','.bat','.cmd','.ps1','.sh','.c','.cpp','.h',
                '.cs','.java','.go','.rs','.rb','.php','.txt','.md','.csv','.tsv'}
TEXT_SUFFIXES.update(CODE_SUFFIXES)
EXTENSIONS = {'python':'.py','py':'.py','javascript':'.js','js':'.js','typescript':'.ts',
              'ts':'.ts','tsx':'.tsx','jsx':'.jsx','html':'.html','css':'.css','json':'.json',
              'yaml':'.yaml','yml':'.yml','sql':'.sql','powershell':'.ps1','ps1':'.ps1',
              'bat':'.bat','batch':'.bat','bash':'.sh','sh':'.sh','c':'.c','cpp':'.cpp',
              'csharp':'.cs','cs':'.cs','java':'.java','go':'.go','rust':'.rs','toml':'.toml'}


@dataclass(frozen=True)
class Fence:
    start: int
    end: int
    language: str
    code: str
    complete: bool

    @property
    def digest(self):
        return hashlib.sha256(self.code.encode('utf-8')).hexdigest()


def fences(text):
    """Top-level Markdown fences. Never interpret code as HTML or a command."""
    lines = text.splitlines(keepends=True)
    offset = 0; opened = None; code = []
    result = []
    for line in lines:
        if opened is None:
            match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)[\r\n]*$', line)
            if match and not (match[1][0]=='`' and '`' in match[2]):
                info=match[2].strip().split()
                opened=(offset,match[1],info[0] if info else 'text')
                code=[]
        else:
            start, marker, language = opened
            if re.fullmatch(r' {0,3}'+re.escape(marker[0])+'{'+str(len(marker))+r',}[ \t]*(?:\r?\n)?',line):
                result.append(Fence(start,offset+len(line),language,''.join(code),True));opened=None
            else:
                code.append(line)
        offset += len(line)
    if opened:
        result.append(Fence(opened[0],len(text),opened[2],''.join(code),False))
    return result


def source_record(raw, limit=12000, with_text=False):
    path=Path(raw).resolve(strict=True)
    if path.suffix.lower() not in CODE_SUFFIXES or not path.is_file():
        return None
    data=path.read_bytes()
    if len(data)>256*1024: return None
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError:return None
    if '\x00' in text:return None
    record={'path':str(path),'name':path.name,'sha256':hashlib.sha256(data).hexdigest(),
            'truncated':len(text)>limit}
    if with_text:record['_text']=text[:limit]
    return record


def suggested_name(language, original=None):
    if original:
        p=Path(original)
        return p.stem+'_edited'+p.suffix
    return 'chat_ai_code'+EXTENSIONS.get(language.lower(),'.txt')


class CodeFiles:
    def __init__(self, roots, backups, audit):
        self.tools=FileTools(roots,backups,audit)

    def source_text(self, record):
        p=Path(record['path']).resolve(strict=True)
        if p.suffix.lower() not in CODE_SUFFIXES or not p.is_file() or p.stat().st_size>256*1024:
            raise ValueError('Chỉ so sánh file văn bản UTF-8 tối đa 256 KB.')
        data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise RuntimeError('File gốc đã thay đổi sau khi gửi. Hãy gửi lại bản mới trước khi sửa.')
        return data.decode('utf-8-sig')

    def prepare(self, target, code, source=None):
        if not isinstance(code,str) or len(code)>100000:
            raise ValueError('Nội dung file tối đa 100000 ký tự.')
        p=self.tools.path(str(target),exists=False)
        if p.suffix.lower() not in CODE_SUFFIXES:
            raise ValueError('Chỉ lưu định dạng văn bản/mã nguồn được hỗ trợ.')
        if source:
            old=self.source_text(source)
            if source.get('truncated'):
                raise ValueError('AI chỉ nhận trích đoạn file. Gửi file nhỏ hơn hoặc yêu cầu bản đầy đủ trước khi ghi đè.')
            if p != Path(source['path']).resolve():
                raise ValueError('File gốc không khớp với file được duyệt.')
        else:
            old=p.read_text(encoding='utf-8-sig') if p.is_file() else ''
        if p.is_file():
            data=p.read_bytes()
            # Preserve UTF-8 BOM and existing CRLF convention on overwrite.
            normalized=code.replace('\r\n','\n')
            if '\r\n' in old:normalized=normalized.replace('\n','\r\n')
            # read_text translates newlines; check original bytes as well.
            elif b'\r\n' in data:normalized=normalized.replace('\n','\r\n')
            code=('\ufeff' if data.startswith(b'\xef\xbb\xbf') else '')+normalized.lstrip('\ufeff')
        plan=self.tools.prepare('file_write',{'path':str(p),'content':code})
        if source and plan['sha256']!=source['sha256']:
            raise RuntimeError('File đã thay đổi. Hãy gửi lại file.')
        return plan

    def commit(self, plan):
        return self.tools.commit(plan)
