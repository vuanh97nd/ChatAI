"""Presentation metadata for files sent with a specific message."""
import base64
import html
from pathlib import Path


def attachment_records(paths):
    return [{'name':Path(path).name,'path':str(path)} for path in paths]


def attachment_html(records):
    blocks=[]
    for record in records if isinstance(records,list) else []:
        if not isinstance(record,dict):continue
        name=record.get('name') or record.get('file')
        if not isinstance(name,str) or not name:continue
        label=html.escape(name)
        path=record.get('path') or record.get('source')
        if isinstance(path,str) and path:
            token=base64.urlsafe_b64encode(path.encode()).decode().rstrip('=')
            label='<a href="chatai-file:'+token+'">'+label+'</a>'
        blocks.append('<p>📎 '+label+'</p>')
    return ''.join(blocks)


def latest_documents(messages):
    for message in reversed(messages or []):
        if message.get('role')=='user' and message.get('documents'):
            return message['documents']
    return []

def source_names(records):
    return {str(r.get('name') or r.get('file') or '').casefold() for r in records if isinstance(r,dict)}-{''}


def document_turn_history(messages):
    """Keep the latest attachment's user thread; previous summaries are not evidence."""
    start=next((i for i in range(len(messages)-1,-1,-1) if messages[i].get('role')=='user' and messages[i].get('documents')),None)
    if start is None:return messages
    records=messages[start:]
    return [m for m in records if m.get('role')=='user' or
            (m.get('role')=='assistant' and any(x in m.get('content','').casefold() for x in ('ocr thất bại','chưa đọc được','không mở được pdf')))]
