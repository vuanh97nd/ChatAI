"""Create a new DOCX in the permitted workspace and open it in authorized Word."""
import uuid
import subprocess
from .office import OfficeTools
from .windows_apps import fingerprint


class WordApp:
    def __init__(self, windows, files):
        self.windows, self.files = windows, files
        self.office = OfficeTools(files)

    def prepare(self, name, args):
        self.windows.check()
        app = self.windows.allowed_path(args['app'])
        if app.name.lower() != 'winword.exe':
            raise ValueError('Chọn WINWORD.EXE từ windows_list_apps.')
        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu tài liệu được phép trong Cài đặt.')
        from pathlib import Path
        requested=args.get('path','').strip()
        path=Path(requested) if requested else self.files.roots[0]/('ChatAI-'+uuid.uuid4().hex+'.docx')
        if requested and not path.is_absolute():path=self.files.roots[0]/path
        path=self.files.path(str(path),exists=False)
        if path.suffix.lower()!='.docx':raise ValueError('Tên file Word phải có đuôi .docx.')
        mode=args.get('mode','new')
        if mode not in ('new','overwrite'):raise ValueError('mode phải là new hoặc overwrite.')
        formatting={'font_name':args.get('font_name','Times New Roman'),'font_size':args.get('font_size','13'),'alignment':args.get('alignment','justify'),'line_spacing':args.get('line_spacing','1.15')}
        document = self.office.prepare('office_overwrite' if mode=='overwrite' else 'office_create', {'path':str(path), 'title':args.get('title',''), 'content':args['content'],**formatting})
        return {'action':'word_create_open', 'app':str(app), 'sha256':fingerprint(app), 'document':document}

    def commit(self, plan):
        self.windows.check()
        app = self.windows.allowed_path(plan['app'])
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('Word đã thay đổi sau khi lập kế hoạch.')
        result = self.office.commit(plan['document'])
        self.windows.check()
        self.windows.allowed_path(str(app))
        subprocess.Popen([str(app),plan['document']['path']], shell=False)
        return {'ok':True, 'path':plan['document']['path'], 'document_created':True,
                'word_launch_requested':True, 'backup':result.get('backup'), 'formatting':{key:plan['document'][key] for key in ('font_name','font_size','alignment','line_spacing')}, 'note':'Đã tạo DOCX có nội dung và gửi lệnh mở Word; chưa xác minh cửa sổ hiển thị.', 'document':result}
