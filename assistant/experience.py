"""Thẻ kinh nghiệm chọn theo nhãn/từ khóa; sổ bước chỉ ghi kết quả công cụ thực."""
import hashlib
import json
import re

# id, nhóm, dấu hiệu, dữ kiện, quy trình, tránh lỗi, ví dụ, điều kiện dừng.
CARD_ROWS = [
 ('startup','coding',r'khởi động|không mở|tự tắt|không chạy', 'Log cuối và thời điểm lỗi','Phân biệt chưa hiện cửa sổ với lỗi sau khi mở; đọc log rồi kiểm tra nguyên nhân đầu tiên','Không cài lại toàn bộ ngay','Tôi cần dòng lỗi cuối trong startup.log để chọn bước kiểm tra đúng.','Chưa có log: hỏi đúng file, không nhận đã chẩn đoán chắc chắn.'),
 ('python_import','coding',r'modulenotfound|importerror|thiếu thư viện','Interpreter và tên module','Đối chiếu Python chạy ứng dụng với môi trường cài thư viện','Không dùng pip của môi trường khác','Dùng python -m pip trong đúng môi trường run.bat.','Chưa biết môi trường: xin đường dẫn interpreter/log.'),
 ('python_version','coding',r'phiên bản python|python 3\.|tương thích','Phiên bản và lỗi cài','Đối chiếu lỗi wheel/dependency; nêu cách kiểm tra','Không tự khẳng định thư viện hỗ trợ mọi phiên bản','Cần xem lỗi cài cụ thể trước khi đổi phiên bản.','Thiếu thông tin: chưa khuyên nâng/hạ hàng loạt.'),
 ('venv','coding',r'venv|pip|cài thư viện','Executable và lệnh đã chạy','Kiểm tra môi trường trước, cài đúng gói bị thiếu','Không lặp cùng lệnh cài thất bại','So sánh python executable với pip đang dùng.','Lỗi mạng/quyền: xử lý nguyên nhân thay vì cài lại.'),
 ('ollama_connection','coding',r'ollama|11434|connection refused','Endpoint và trạng thái dịch vụ','Kiểm tra kết nối local rồi model được chọn','Không tải model khi lỗi chỉ do dịch vụ chưa chạy','Kiểm tra Ollama đang chạy trước.','Chưa kết nối: không kết luận model thiếu.'),
 ('latency','coding',r'lag|chậm|rất lâu|tốc độ','Thời gian nạp/ra token/hoàn tất','Tách chi phí nạp, context, tool, review; thay từng yếu tố','Không hứa nhanh hơn khi chưa đo','Đo thời gian câu ngắn và câu có RAG riêng.','Chưa có số đo: nêu đây là giả thuyết.'),
 ('gpu','coding',r'gpu|vram|cuda|out of memory','Log bộ nhớ và cấu hình','Kiểm tra tải GPU/context; ưu tiên giảm tải phù hợp','Không mặc định GPU đang được dùng','Cần log cho biết phần nào chạy GPU/CPU.','Không có log: không nhận lỗi do VRAM chắc chắn.'),
 ('download','coding',r'tải.*chậm|không tải|download|xoay','Tiến độ byte và lỗi cuối','Phân biệt chờ kết nối, tải, giải nén; chỉ tiếp tục khi biết nguyên nhân','Không xóa cache vô điều kiện','Xem byte đã tải và lỗi mạng cuối.','Thao tác xóa/cài lại cần quyền xác nhận.'),
 ('traceback','coding',r'traceback|exception|lỗi code','Traceback và phần code liên quan','Đọc exception cuối, truy đến dòng gây lỗi, sửa tối thiểu','Không bịa cấu trúc dự án','Gửi phần traceback từ dòng Traceback đến lỗi cuối.','Thiếu code: hỏi phần liên quan.'),
 ('code_test','coding',r'kiểm thử|test|unit test','Yêu cầu và đầu vào biên','Đưa test có ý nghĩa; chạy nếu có quyền/công cụ','Không nói test qua khi chưa chạy','Tôi đã viết test; chưa có kết quả chạy trong môi trường đích.','Công cụ không có: nêu giới hạn.'),
 ('patch','coding',r'sửa code|sửa mã|sửa file','File thực và lỗi','Đọc bản hiện tại, thay đúng phần, kiểm tra tác động','Không sửa khi chỉ được yêu cầu đề xuất','Sau khi được phép tôi sẽ sửa file hiện có.','Chưa có file: xin đúng file cần xem.'),
 ('sql','coding',r'sql|database|sqlite','Hệ SQL và schema','Nêu giả định, kiểm tra truy vấn đọc trước','Không đoán cột hoặc chạy xóa hàng loạt','Cần tên bảng/cột hoặc schema để viết đúng truy vấn.','Thao tác ghi cần xác nhận.'),
 ('excel','personal_documents',r'excel|xlsx|sheet','File/sheet/range','Liệt kê khi chưa biết; đọc đúng vùng, xem kiểu dữ liệu','Không bịa ô hoặc kết quả công thức','Tôi sẽ đọc vùng liên quan trước khi sửa.','Chưa có file/whitelist: xin vị trí.'),
 ('excel_formula','personal_documents',r'công thức|formula|cache','Công thức và dữ liệu gốc','Phân biệt công thức với cache; đối chiếu ô tham chiếu','Không coi cache cũ là tính mới','Giá trị cache có thể chưa cập nhật trong Excel.','Chưa tính lại: không nhận kết quả mới.'),
 ('geoslope_bth_su','engineering',r'geo[\s-]?(?:slope|studio)|slope/w','Hồ sơ Km 134+300; SLTT/BTH; lớp và đơn vị','Hồ sơ này: lớp 1a tạm giữ GeoStudio hiện có (gamma 16.1, Co/Su 14.7, UndrainedPhiZero, phi=0). Hàng 13 BTH mới là Co VST; lớp 1c dùng E13=15.10 kN/m2 như Su, UndrainedPhiZero, phi=0. Hàng 4 là c DST (1c c=4.86 kN/m2 theo người dùng), hàng 6 là phi DST; không dùng c DST khi đã có Co VST. Các lớp khác ưu tiên Co VST hàng 13, thiếu Co thì dùng c/phi DST.','Không thay 1a bằng thí nghiệm; không coi hàng 4 là Co; không dùng c=4.86 thay Co VST 15.10 cho 1c; giữ nguyên workbook để người dùng tự sửa nhãn.','Co hàng 13 VST dùng như Su; c hàng 4/phi hàng 6 là DST.','Chỉ Solve trên bản sao; ghi input/log và đọc Fs từ kết quả mới.'),
 ('office','personal_documents',r'word|docx|pptx|powerpoint','Tệp và nội dung cần sửa','Đọc nội dung, giữ cấu trúc, preview thao tác','Không nhận giữ mọi định dạng nếu tool không hỗ trợ','Nêu rõ phần định dạng có thể thay đổi.','Giới hạn tool: thông báo trước.'),
 ('pdf_scan','personal_documents',r'pdf|scan|ocr','PDF có text hay ảnh','Kiểm tra trích text; nếu scan cần OCR phù hợp','Không đoán chữ hoặc số mờ','Chưa có văn bản trích được; cần OCR hoặc bản text.','OCR chưa có: không nhận đã đọc.'),
 ('document_id','current_web',r'tccs|tcvn|qcvn|tiêu chuẩn','Mã/năm/cơ quan ban hành','Nếu web bật: tìm các cách viết mã, đối chiếu rồi đọc','Không nhận tài liệu gần giống là đúng','Nguồn hiển thị mã này; cơ quan ban hành còn cần đối chiếu.','Web tắt/thiếu file: xin bật nút hoặc gửi file.'),
 ('document_partial','personal_documents',r'tóm tắt|nội dung chính|tài liệu','Phạm vi văn bản thực có','Nêu phần đọc được, tóm tắt yêu cầu cụ thể kèm đoạn nguồn','Không tóm tắt toàn văn từ snippet','Bản tóm tắt chỉ dựa trên phần đã truy xuất.','Nguồn thiếu: nêu phần chưa có.'),
 ('source_conflict','current_web',r'mâu thuẫn|đối chiếu|khác nhau','Nguồn và thời điểm','So sánh phạm vi/phiên bản/ngày cập nhật','Không gộp số khác nhau thành một đáp án','Hai nguồn dùng phạm vi khác nhau nên chưa so trực tiếp được.','Chưa đủ căn cứ: giữ kết luận mở.'),
 ('news','current_web',r'tin tức|mới nhất|hôm nay','Ngày sự kiện và ngày đăng','Chỉ khi web bật: đọc nguồn, phân biệt ngày đăng/ngày xảy ra','Không gọi tin cũ là mới','Nêu thời điểm và nguồn của bản tin.','Web tắt: chưa xác minh thông tin mới.'),
 ('weather','current_web',r'thời tiết|nhiệt độ|mưa','Địa điểm và thời điểm','Chỉ khi web bật: tra dữ liệu đúng địa điểm','Không bịa số liệu dự báo','Nếu thiếu địa điểm, hỏi tên thành phố.','Chưa có kết quả: không đưa số đo hiện tại.'),
 ('web_failure','current_web',r'không tìm|không đọc|bị chặn|403|404','URL và lỗi truy xuất','Thử nguồn khác có lý do, giữ giới hạn lượt','Không lặp yêu cầu thất bại vô hạn','Trang bị chặn; nguồn khác có thể chỉ cung cấp trích đoạn.','Web tắt hoặc hết giới hạn: dừng tra.'),
 ('percent','calculation',r'phần trăm|giảm giá|lãi suất|%','Giá trị gốc, tỷ lệ, thời kỳ','Dùng calculate với tỷ lệ/100, nêu đơn vị','Không dùng modulo làm phần trăm','Công thức được đưa vào calculate trước khi nêu đáp số.','Thiếu giá gốc/tỷ lệ: hỏi dữ kiện.'),
 ('units','calculation',r'đổi|đơn vị|km|kg|độ c|độ f','Đơn vị gốc và đích','Kiểm tra cùng đại lượng, dùng tool đổi đơn vị','Không trả số thiếu đơn vị','Cần biết đơn vị gốc và đơn vị muốn đổi.','Đơn vị không hỗ trợ: nêu giới hạn.'),
 ('dates','calculation',r'ngày|tháng|giờ|múi giờ','Ngày ISO/múi giờ/quy ước','Dùng công cụ; nêu có tính ngày đầu hay không','Không đoán ngày mơ hồ','Chênh ngày dùng end-start, không cộng ngày đầu.','Định dạng mơ hồ: hỏi rõ.'),
 ('statistics','calculation',r'trung bình|trung vị|thống kê','Tập số và giá trị thiếu','Dùng tool, nêu cách xử lý dữ liệu thiếu','Không tự loại ngoại lệ không có lý do','Trung bình và trung vị được tính từ cùng tập dữ liệu.','Thiếu tập số: xin dữ liệu.'),
 ('translation','writing_translation',r'dịch|translate','Ngôn ngữ và sắc thái','Giữ nghĩa, số liệu, mức độ chắc chắn','Không tự thêm lý do hoặc sự kiện','Chỉ chú thích khi từ gốc có nhiều nghĩa.','Thiếu văn bản: xin đoạn cần dịch.'),
 ('email','writing_translation',r'email|thư|báo cáo','Đối tượng và mục đích','Đưa bản hoàn chỉnh, placeholder cho dữ kiện thiếu','Không bịa tên/ngày/sự kiện','Dùng [Tên người nhận] nếu chưa được cung cấp.','Thiếu mục tiêu quan trọng: hỏi ngắn.'),
 ('advice','knowledge',r'kế hoạch|nên chọn|phương án|ngân sách','Mục tiêu/nguồn lực đã có','Chọn phương án phù hợp, ưu nhược và bước đầu','Không hứa kết quả chắc chắn','Nêu vì sao phương án phù hợp với giới hạn đã cung cấp.','Thiếu ràng buộc quyết định: hỏi đúng điểm.'),
 ('high_stakes','knowledge',r'thuốc|bệnh|pháp lý|đầu tư|tài chính','Dữ kiện/điều kiện áp dụng','Thông tin cụ thể, giới hạn rõ; rà soát khi cần','Không kê kết luận chắc chắn hoặc hứa lợi nhuận','Nêu điều cần xác minh và khi nào cần chuyên gia.','Thiếu dữ kiện an toàn quan trọng: không đoán.'),
 ('memory','knowledge',r'ghi nhớ|sở thích|nhớ rằng','Yêu cầu ghi nhớ thật','Chỉ lưu theo quyền; chỉ dùng ký ức liên quan','Không nhận model tự học hoặc suy đoán hồ sơ','Ghi nhớ là lưu/truy xuất dữ liệu, không đổi trọng số.','Bí mật hoặc tài khoản khác: không lưu/dùng.'),
 ('explain','knowledge',r'giải thích|hướng dẫn|không hiểu','Mức hiểu và mục tiêu','Kết luận trước, ví dụ đơn giản, bước vừa đủ','Không hỏi lại dữ kiện đã có','Giải thích thuật ngữ trước khi dùng trong ví dụ.','Không chắc dữ kiện: nói rõ giới hạn.'),
]

CARDS=[dict(zip(('id','category','trigger','needed','steps','avoid','example','stop'),row)) for row in CARD_ROWS]


def fingerprint(name,args):
    return hashlib.sha256((name+json.dumps(args,sort_keys=True,ensure_ascii=False,default=str)).encode()).hexdigest()[:24]


def tool_attempts(messages,current_turn=False):
    if current_turn:
        boundary=next((i for i in range(len(messages)-1,-1,-1) if messages[i].get('role')=='user'),0)
        messages=messages[boundary:]
    else:messages=messages[-60:]
    pending=[];rows=[]
    for message in messages:
        if message.get('role')=='assistant':
            pending.extend(message.get('tool_calls') or [])
        elif message.get('role')=='tool':
            name=message.get('tool_name','')
            call=next((x for x in pending if x.get('function',{}).get('name')==name),None)
            if call:pending.remove(call)
            try:result=json.loads(message.get('content',''))
            except (ValueError,TypeError):result={}
            if not isinstance(result,dict):result={}
            outcome='denied' if result.get('denied') else 'success' if result.get('ok') is True else 'failed' if result.get('ok') is False or result.get('error') else 'observed'
            args=call.get('function',{}).get('arguments',{}) if call else None
            error=str(result.get('error',''))[:160]
            error=re.sub(r'(?i)(password|token|secret|api_key)\s*[:=]\s*\S+',r'\1=[ẩn]',error)
            rows.append({'tool':name,'signature':fingerprint(name,args) if args is not None else None,'outcome':outcome,'error':error})
    return rows[-12:]


def task_record(state):
    messages=state.get('messages',[])
    question=next((m.get('content','') for m in reversed(messages) if m.get('role')=='user'),'')
    explicit_pause=bool(re.search(r'chỉ đề xuất|trao đổi trước|chưa sửa|đừng sửa|nói trước',question,re.I))
    explicit_action=bool(re.search(r'hãy sửa|sửa nhé|sửa mã|hãy thực hiện|rồi thực hiện|rồi sửa',question,re.I))
    discuss=explicit_pause or (bool(re.search(r'đề xuất|ý tưởng',question,re.I)) and not explicit_action)
    return {'phase':'discussion' if discuss else 'requested',
        'instruction':'Giai đoạn trao đổi: chưa sửa/chạy thao tác ghi.' if discuss else 'Yêu cầu hiện tại không tự cấp quyền vượt xác nhận UI/whitelist.',
        'attempts':tool_attempts(messages),
        'note':'Chỉ kết quả công cụ là bằng chứng đã làm; lời AI trước đây không chứng minh thao tác.'}


def repeated_failure(state,call):
    fn=call['function'];signature=fingerprint(fn['name'],fn['arguments'])
    matches=[row for row in tool_attempts(state.get('messages',[]),True) if row['signature']==signature]
    if any(row['outcome']=='denied' for row in matches):return 'Thao tác giống hệt đã bị từ chối trong lượt này; không đề nghị lại.'
    if sum(row['outcome']=='failed' for row in matches)>=2:
        return 'Cùng công cụ và tham số đã thất bại hai lần; cần đổi cách xử lý có căn cứ hoặc hỏi dữ kiện thiếu.'
    return None


def select_cards(question,route,record,max_chars=1100):
    if not isinstance(question,str) or not re.search(r'geo[\s-]?(?:slope|studio)|slope/w',question,re.I):
        return []
    if not re.search(r'km\s*134\s*\+\s*300|sltt\.xlsx|bth\s*\(2\)',question,re.I):
        return []
    card=next(c for c in CARDS if c['id']=='geoslope_bth_su')
    return [card] if len(json.dumps(card,ensure_ascii=False))<=max_chars else []
