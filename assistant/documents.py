"""Đọc HTML/PDF/DOCX/TXT với nhãn phạm vi, trang và giới hạn tài nguyên rõ ràng."""
from io import BytesIO
import base64
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

MAX_BYTES=20*1024**2
MAX_TEXT=1_000_000
MAX_PAGES=1500
MAX_OCR_PAGES=200


def pdf_vision_ocr(client, model='gemma3:4b', *, num_ctx=4096):
    """Return a callback that locally renders and reads a scanned PDF page with Ollama vision."""
    cached_pdf=None;cached_raw=None
    def read_page(raw, page_index):
        nonlocal cached_pdf,cached_raw
        try:
            import pypdfium2 as pdfium
            if cached_pdf is None or cached_raw!=raw:
                if cached_pdf is not None:cached_pdf.close()
                cached_pdf=pdfium.PdfDocument(raw);cached_raw=raw
            page=cached_pdf[page_index]
            page_width,page_height=page.get_size()
            scale=min(2.0,2400.0/max(page_width,page_height,1.0))
            bitmap=page.render(scale=scale)
            image=bitmap.to_pil().convert('RGB')
            output=BytesIO();image.save(output,format='JPEG',quality=88,optimize=True)
            encoded=base64.b64encode(output.getvalue()).decode('ascii')
            response=client.chat(model=model,stream=False,keep_alive='10m',
                messages=[
                    {'role':'system','content':(
                        'Bạn đang chép chữ từ một trang PDF scan. Chép lại nội dung nhìn thấy bằng tiếng Việt hoặc ngôn ngữ gốc; '
                        'giữ số liệu, đơn vị, tên riêng và thứ tự. Bảng thì trình bày thành bảng Markdown. '
                        'Chỗ không đọc chắc ghi [không rõ]. Không tóm tắt, không suy đoán, không thêm nội dung.' )},
                    {'role':'user','content':f'Đọc nguyên văn trang {page_index+1}.','images':[encoded]},
                ],options={'temperature':0.0,'num_ctx':min(4096,num_ctx),'num_predict':3000})
            message=response['message'] if isinstance(response,dict) else response.message
            text=message['content'] if isinstance(message,dict) else message.content
            return str(text or '').strip()
        except Exception as error:
            raise ValueError(f'Không OCR được trang {page_index+1} bằng AI đọc ảnh {model}: {error}') from error
    return read_page


class MainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[];self.main=[];self.hidden=0;self.depth=0;self.title=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','nav','footer','header'):self.hidden+=1
        if tag in ('main','article'):self.depth+=1
        if tag=='title':self.in_title=True
        if tag in ('p','br','div','h1','h2','h3','li','tr'):self.handle_data('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','nav','footer','header'):self.hidden=max(0,self.hidden-1)
        if tag in ('main','article'):self.depth=max(0,self.depth-1)
        if tag=='title':self.in_title=False
        if tag in ('p','div','h1','h2','h3','li','tr'):self.handle_data('\n')
    def handle_data(self,data):
        if self.in_title:self.title.append(data);return
        if not self.hidden:
            self.parts.append(data)
            if self.depth:self.main.append(data)
    def text(self):
        raw=''.join(self.main if self.main else self.parts)
        return re.sub(r'\n\s*\n+', '\n\n',re.sub(r'[ \t]+',' ',raw)).strip()


def _is_garbled(text):
    """Return True when text is mostly PDF font-encoding artifacts like '/0 /1 /2'."""
    tokens=text.split()
    if len(tokens)<4:return False
    slash_codes=sum(1 for t in tokens if re.match(r'^/\w{1,6}$',t))
    return slash_codes/len(tokens)>0.4


def read_bytes(raw,kind='',name='document',pdf_ocr=None):
    if len(raw)>MAX_BYTES:raise ValueError('Tài liệu vượt giới hạn 20 MiB; không đọc một phần rồi nhận là toàn văn.')
    ext=Path(name).suffix.casefold();units=[];issues=[];title=''
    ocr_pages=[]
    if raw.startswith(b'%PDF-') or ext=='.pdf' or 'application/pdf' in kind:
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(raw))
        if reader.is_encrypted:raise ValueError('PDF mã hóa; cần bản có thể đọc.')
        total=len(reader.pages);size=0
        ocr_limit_reported=False
        for index,page in enumerate(reader.pages[:MAX_PAGES],1):
            text=page.extract_text() or ''
            if not text.strip() or _is_garbled(text):
                text=''
                if pdf_ocr and len(ocr_pages)<MAX_OCR_PAGES:
                    text=pdf_ocr(raw,index-1) or ''
                    if text.strip():ocr_pages.append(index)
                    elif getattr(pdf_ocr,'skip_reason',''):
                        if not ocr_limit_reported:
                            issues.append(f'Từ trang {index}: '+pdf_ocr.skip_reason)
                            ocr_limit_reported=True
                    else:issues.append(f'Trang {index} đã gửi OCR nhưng không nhận được chữ.')
                elif pdf_ocr:
                    if not ocr_limit_reported:
                        issues.append(f'Đã chạm giới hạn OCR {MAX_OCR_PAGES} trang; các trang scan còn lại chưa đọc.')
                        ocr_limit_reported=True
                else:
                    issues.append(f'Trang {index} không có text trích xuất; cần OCR.')
            units.append({'location':f'trang {index}','page':index,'text':text,'ocr':index in ocr_pages})
            size+=len(text)
            if size>MAX_TEXT:issues.append('Vượt giới hạn 1 triệu ký tự.');break
        if len(units)<total:issues.append(f'Đã đọc {len(units)}/{total} trang.')
        format_name='pdf'
        title=str((reader.metadata or {}).get('/Title',''))[:300]
    elif ext=='.docx' or 'wordprocessingml' in kind:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            members=archive.infolist()
            if len(members)>10000 or sum(x.file_size for x in members)>60*1024**2:
                raise ValueError('DOCX giải nén vượt giới hạn an toàn.')
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            parts=['word/document.xml']+[x.filename for x in members if re.fullmatch(r'word/(?:footnotes|endnotes|comments|header\d+|footer\d+)\.xml',x.filename)]
            size=0
            for part in parts:
                node=ET.fromstring(archive.read(part))
                for index,para in enumerate(node.findall('.//w:p',ns),1):
                    text=''.join(x.text or '' for x in para.findall('.//w:t',ns))
                    location=f'đoạn {index}' if part=='word/document.xml' else f'{Path(part).name}, đoạn {index}'
                    if text.strip():units.append({'location':location,'text':text})
                    size+=len(text)
                    if size>MAX_TEXT:issues.append('Vượt giới hạn 1 triệu ký tự.');break
                if size>MAX_TEXT:break
        format_name='docx'
    else:
        content=raw.decode('utf-8-sig',errors='replace')
        if 'html' in kind or re.search(r'<(?:!doctype html|html|body)\b',content[:2000],re.I):
            parser=MainHTML();parser.feed(content);text=parser.text();title=''.join(parser.title).strip()[:300]
            format_name='html'
        else:text=content;format_name='text'
        if len(text)>MAX_TEXT:issues.append('Vượt giới hạn 1 triệu ký tự.')
        units=[{'location':f'đoạn {i}','text':x} for i,x in enumerate(re.split(r'\n\s*\n',text[:MAX_TEXT]),1) if x.strip()]
    if not units or not any(x['text'].strip() for x in units):
        if pdf_ocr:
            if getattr(pdf_ocr,'skip_reason',''):raise ValueError(pdf_ocr.skip_reason)
            raise ValueError('PDF không có lớp chữ và OCR không nhận diện được chữ. Hãy dùng bản scan rõ hơn hoặc kiểm tra dịch vụ AI đọc ảnh đã chọn.')
        raise ValueError('PDF không có lớp chữ trích xuất; cần bật luồng OCR cục bộ trước khi tóm tắt.')
    combined='\n\n'.join('['+x['location']+']\n'+x['text'] for x in units)
    coverage_parts=[]
    if ocr_pages:
        coverage_parts.append(f'{len(ocr_pages)} trang scan đã OCR bằng {getattr(pdf_ocr, "source", "AI đọc ảnh cục bộ")}; ký tự và số liệu OCR có thể sai, cần đối chiếu bản gốc.')
    coverage_parts.extend(issues[:4])
    coverage_note=' '.join(coverage_parts) or 'Đã trích xuất hết phần văn bản có thể đọc từ tệp.'
    return {'text':combined,'units':units,'title':title,'format':format_name,'ocr_pages':ocr_pages,
        'full_text':not issues,'truncated':bool(issues),'issues':issues,
        'coverage':'full_text' if not issues else 'partial',
        'coverage_note':coverage_note}


def read_local(path,pdf_ocr=None,foxit_ocr=False):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>MAX_BYTES:raise ValueError('Tệp không hợp lệ hoặc vượt 20 MiB.')
    try:
        result=read_bytes(p.read_bytes(),name=p.name,pdf_ocr=pdf_ocr)
        return {**result,'file':p.name,'source':str(p)}
    except ValueError as exc:
        if foxit_ocr and 'OCR' in str(exc) and p.suffix.lower()=='.pdf':
            from assistant.foxit_ocr_automation import foxit_ocr as _foxit_ocr,available as _foxit_available
            if not _foxit_available():
                raise ValueError('OCR cục bộ không khả dụng: cần Windows và thư viện pywinauto (pip install pywinauto).')
            try:
                ocr_path=_foxit_ocr(p)
            except Exception as foxit_err:
                raise ValueError(f'Foxit OCR thất bại: {foxit_err}') from foxit_err
            result=read_bytes(ocr_path.read_bytes(),name=ocr_path.name,pdf_ocr=pdf_ocr)
            return {**result,'file':ocr_path.name,'source':str(ocr_path),'foxit_ocr':True}
        raise


def chunks(document,max_chars=6000):
    """Bao phủ mọi đơn vị chữ; từng chunk giữ vị trí gốc và ID chứng cứ."""
    rows=document.get('units') or [{'location':'nội dung','text':document.get('text','')}]
    text='';locations=[];page_numbers=[];number=0
    for unit in rows:
        raw=unit.get('text','')
        for start in range(0,len(raw),max_chars-150):
            piece=raw[start:start+max_chars-150]
            if text and len(text)+len(piece)+100>max_chars:
                number+=1
                yield {'index':number,'text':text,'locations':list(dict.fromkeys(locations)),
                       'pages':list(dict.fromkeys(page_numbers))}
                text='';locations=[];page_numbers=[]
            text+='['+unit.get('location','nội dung')+']\n'+piece+'\n'
            locations.append(unit.get('location','nội dung'))
            if unit.get('page'):page_numbers.append(unit['page'])
    if text:
        number+=1
        yield {'index':number,'text':text,'locations':list(dict.fromkeys(locations)),
               'pages':list(dict.fromkeys(page_numbers))}


def read_document_range(files,path,start=0,limit=6000,pdf_ocr=None,foxit_ocr=False):
    """Tool đọc theo offset, có thể đọc tiếp đến hết; không gọi mạng."""
    p=files.path(path)
    if p.suffix.lower() not in ('.pdf','.docx','.txt','.md','.html'):
        raise ValueError('PDF/DOCX/TXT/MD/HTML; Excel dùng excel_read.')
    if type(start) is not int or start<0 or type(limit) is not int or not 1<=limit<=8000:
        raise ValueError('start >= 0, limit 1..8000.')
    document=read_local(p,pdf_ocr=pdf_ocr,foxit_ocr=foxit_ocr);offset=0;locations=[]
    for unit in document['units']:
        length=len('['+unit['location']+']\n'+unit['text'])
        if offset+length>start and offset<start+limit:locations.append(unit['location'])
        offset+=length+2
    text=document['text'];end=min(len(text),start+limit)
    return {'ok':True,'path':str(p),'content':text[start:end],'locations':locations,
        'characters_total':len(text),'next_start':end if end<len(text) else None,
        'range_start':start,'range_end':end,'truncated':start>0 or end<len(text),
        'coverage':'full_text' if start==0 and end==len(text) and document['full_text'] else 'partial',
        'note':document['coverage_note'],'issues':document.get('issues',[])}
