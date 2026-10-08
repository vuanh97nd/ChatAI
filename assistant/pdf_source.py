"""Approved PDF download and Foxit opening; text extraction is independent of the UI."""
import io
from pathlib import Path
import subprocess
import uuid
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .browser import public_url
from .windows_apps import fingerprint


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


class PDFSource:
    def __init__(self,windows,files,audit,pdf_ocr=None):
        self.windows,self.files,self.audit=windows,files,audit
        self.pdf_ocr=pdf_ocr

    def prepare(self,name,args):
        if name=='pdf_read':
            path=self.files.path(args['path'])
            if path.suffix.lower()!='.pdf':raise ValueError('Chỉ đọc PDF.')
            start=int(args.get('start','0'))
            if start<0:raise ValueError('start phải không âm.')
            return {'action':name,'path':str(path),'sha256':fingerprint(path),'start':start,
                    'notice':'Đọc tối đa 8000 ký tự PDF tại vị trí start và đưa vào hội thoại AI.'}
        app=self.windows.allowed_path(args['app'])
        if app.name.lower() not in {'foxitpdfreader.exe','foxitreader.exe','foxit reader.exe','foxitpdfeditor.exe','foxit pdf editor.exe'}:
            raise ValueError('Chọn EXE Foxit PDF Reader hoặc Foxit PDF Editor trong danh sách app được phép.')
        if name=='pdf_local_open':
            path=self.files.path(args['path'])
            if path.suffix.lower()!='.pdf' or path.stat().st_size>20*1024**2:raise ValueError('Chỉ mở PDF tối đa 20 MiB.')
            return {'action':name,'app':str(app),'sha256':fingerprint(app),'path':str(path),'file_sha256':fingerprint(path),
                    'notice':'Mở PDF có sẵn bằng Foxit và đọc phần đầu vào hội thoại; không sửa bản gốc.'}
        url=public_url(args['url'])
        if not self.files.roots:raise PermissionError('Thêm thư mục được phép trong Cài đặt trước.')
        destination=self.files.path(str(self.files.roots[0]/('source-'+uuid.uuid4().hex+'.pdf')),exists=False)
        return {'action':'pdf_source_open','app':str(app),'sha256':fingerprint(app),
                'url':url,'path':str(destination),
                'notice':'Tải PDF tối đa 20 MiB từ URL này, lưu tệp mới trong thư mục được phép, đọc phần đầu rồi mở ứng dụng Foxit đã chọn. Cần duyệt trước; nội dung PDF được gửi cho AI. Không ghi đè file.'}

    def read(self,path,start=0):
        from .documents import read_document_range
        try:
            result=read_document_range(self.files,str(path),start=start,limit=8000,pdf_ocr=self.pdf_ocr,foxit_ocr=self.pdf_ocr is None)
            return dict(result,read_ok=True)
        except (ValueError, RuntimeError) as error:
            return {'ok':False,'read_ok':False,'path':str(path),'content':'','coverage':'none',
                    'next_start':None,'issues':[str(error)],'note':'Chưa đọc được văn bản PDF: '+str(error)+'. OCR tự động không hoàn tất; không lặp lại thao tác lỗi trong lượt này.'}

    def commit(self,plan):
        if plan['action']=='pdf_read':
            path=self.files.path(plan['path'])
            if fingerprint(path)!=plan['sha256']:raise PermissionError('PDF đã đổi; duyệt lại.')
            return self.read(path,plan['start'])
        app=self.windows.allowed_path(plan['app'])
        if fingerprint(app)!=plan['sha256']:raise PermissionError('Foxit đã đổi; duyệt lại.')
        if plan['action']=='pdf_local_open':
            path=self.files.path(plan['path'])
            if fingerprint(path)!=plan['file_sha256']:raise PermissionError('PDF đã đổi; duyệt lại.')
            self.windows.check()
            process=subprocess.Popen([str(app),str(path)],cwd=str(app.parent),shell=False)
            self.audit('pdf_local_open',{'path':str(path),'pid':process.pid})
            return dict(self.read(path),foxit_launch_requested=True,
                        note='Đã gửi lệnh mở Foxit; chưa xác minh cửa sổ. Text trích bằng thư viện PDF; dùng pdf_read với next_start để đọc tiếp.')
        path=self.files.path(plan['path'],exists=False)
        if path.exists() or not path.parent.is_dir():raise ValueError('Đích đã tồn tại hoặc thư mục không hợp lệ.')
        url=public_url(plan['url'])
        request=Request(url,headers={'User-Agent':'ChatAI-PDF/1.0','Accept':'application/pdf'})
        with build_opener(PublicRedirect()).open(request,timeout=25) as response:
            final_url=public_url(response.geturl())
            raw=response.read(20*1024**2+1)
        if len(raw)>20*1024**2 or not raw.startswith(b'%PDF-'):
            raise ValueError('Nguồn không phải PDF hoặc vượt 20 MiB. Có thể là trang đăng nhập/CAPTCHA.')
        from pypdf import PdfReader
        document=PdfReader(io.BytesIO(raw))
        if document.is_encrypted:raise ValueError('PDF mã hóa chưa hỗ trợ.')
        self.windows.check()
        with path.open('xb') as stream:stream.write(raw)
        result=self.read(path)
        # Recheck permission and executable after network/extraction; no shell or arbitrary arguments.
        app=self.windows.allowed_path(plan['app'])
        if fingerprint(app)!=plan['sha256']:raise PermissionError('Foxit đã đổi; PDF đã lưu nhưng chưa mở.')
        process=subprocess.Popen([str(app),str(path)],cwd=str(app.parent),shell=False)
        self.audit('pdf_source_open',{'path':str(path),'source_url':final_url,'pid':process.pid})
        return dict(result,ok=True,path=str(path),source_url=final_url,downloaded=True,foxit_launch_requested=True,
                    note='PDF đã lưu; đã gửi lệnh mở Foxit, chưa xác minh cửa sổ. Văn bản được trích bằng thư viện PDF, không đọc từ màn hình Foxit. Đọc tiếp bằng pdf_read với next_start; không tuyên bố đọc toàn văn khi còn truncated/next_start. PDF scan có thể không có text.')
