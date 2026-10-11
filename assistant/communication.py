"""User-selected communication methods, separate from task execution permission."""
METHODS={
 'com':('COM / OLE — Excel, Word, PowerPoint, AutoCAD',True,True),
 'application_api':('API / SDK riêng — PLAXIS',True,True),
 'uia':('Windows UI Automation — nút, menu, ô nhập',True,True),
 'win32':('Win32 — mở và chọn cửa sổ',True,True),
 'input':('Chuột, bàn phím — thao tác giao diện',True,True),
 'clipboard':('Clipboard — đọc, sao chép và dán văn bản',True,False),
 'screen':('Ảnh màn hình — quan sát cửa sổ',True,True),
 'files':('Đọc / ghi file — XLSX, DOCX, CSV, DXF',True,True),
 'browser':('Trình duyệt — Playwright',True,True),
 'script':('Python — chạy mã trong Docker',True,True),
 'cli':('Dòng lệnh — các lệnh hỗ trợ trong Docker',True,True),
 'plugin':('Plugin / Add-in — Office và cầu nối ứng dụng',True,False),
 'macro':('VBA / AutoLISP — chạy trong Office và AutoCAD',True,False),
 'http':('HTTP / WebSocket — các kết nối đã cấu hình',True,False),
 'ipc':('IPC — TCP nội bộ và Windows named pipe',True,False),
}

class MethodRequired(PermissionError):pass

def validate_methods(cfg):
    selected=cfg.setdefault('communication_methods',{})
    if not isinstance(selected,dict) or any(k not in METHODS or type(v) is not bool for k,v in selected.items()):
        raise ValueError('Phương thức kết nối phải có giá trị bật/tắt hợp lệ.')
    cfg['communication_methods']={k:selected.get(k,default) for k,(_,_,default) in METHODS.items()}

def method_for(tool):
    if tool=='windows_clipboard':return 'clipboard'
    if tool in ('application_connections','plugin_call','office_addin'):return 'plugin' if tool!='application_connections' else None
    if tool in ('vba_execute','autolisp_execute'):return 'macro'
    if tool in ('application_http','application_websocket'):return 'http'
    if tool=='application_ipc':return 'ipc'
    if tool in ('excel_com','word_com','powerpoint_com','autocad_com'):return 'com'
    if tool in ('plaxis_commands','plaxis_run_problem','geoslope_solve','geoslope_materials'):return 'application_api'
    if tool in ('windows_inspect','windows_action'):return 'uia'
    if tool=='windows_input':return 'input'
    if tool=='windows_capture':return 'screen'
    if tool.startswith('windows_'):return 'win32'
    if tool.startswith('browser_'):return 'browser'
    if tool in ('python_run','python_search'):return 'script'
    if tool=='run_command':return 'cli'
    if tool.startswith(('excel_','file_','office_','word_','template_','document_','pdf_','cad_','cad3d_','source_','plaxis_generate')):return 'files'
    return None

def require_method(cfg,tool):
    key=method_for(tool)
    if key is None:return
    label,supported,default=METHODS[key]
    if not supported:raise MethodRequired('Phương thức '+label+'; cần bổ sung công cụ kết nối.')
    if not cfg.get('communication_methods',{}).get(key,default):
        raise MethodRequired('Cần bật phương thức '+label+' để thực hiện '+tool+
          '. Vào Cài đặt → Phương thức kết nối, bật mục này rồi Lưu cài đặt và gửi lại yêu cầu. Chưa thực hiện thao tác.')

def method_status(cfg):
    active=[];disabled=[]
    for k,(label,supported,default) in METHODS.items():
        if supported:(active if cfg.get('communication_methods',{}).get(k,default) else disabled).append(label)
    return ('Phương thức đang bật: '+', '.join(active)+'. Đang tắt: '+', '.join(disabled)+
      '. Nếu cần phương thức đang tắt, nói rõ cần bật mục nào trong Cài đặt → Phương thức kết nối; không tự bật và không lặp công cụ bị chặn. '+
      'Plugin và các giao thức cần kết nối đã cấu hình: dùng application_connections để xem; không đoán địa chỉ, action hoặc tên pipe. VBA cần Trust Center cho phép truy cập VBA Project; AutoCAD VBA cần VBA Enabler nếu dùng VBA. Không tự đổi thiết lập bảo mật của ứng dụng.')


CONNECTION_WRITES = frozenset(('plugin_call','application_http','application_websocket',
    'application_ipc','vba_execute','autolisp_execute','office_addin','windows_clipboard',
    'excel_com','word_com','powerpoint_com','autocad_com'))

def connection_failure_answer(name,result):
    """Stop the turn when replay could duplicate a native or remote write."""
    if name not in CONNECTION_WRITES or result.get('ok'):return None
    if result.get('method_required'):return result.get('error','Cần bật phương thức kết nối.')
    if result.get('uncertain'):
        return 'Chưa xác minh được kết quả: '+str(result.get('error','Ứng dụng chưa xác nhận hoàn tất.'))+' Kiểm tra dữ liệu trong ứng dụng trước khi gửi lại lệnh.'
    return None
