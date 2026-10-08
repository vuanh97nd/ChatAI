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
