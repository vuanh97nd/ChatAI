WRITES = {"excel_edit_cell", "file_write", "file_edit", "file_move", "file_delete", "image_resize", "video_from_images",
          "python_run", "python_search", "run_command", "rag_index", "image_generate", "video_generate", "office_create", "word_replace", "windows_open", "windows_inspect", "windows_action", "browser_search", "browser_run"}
WRITES.update({'pdf_source_open','pdf_read'})

def schema(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False}}}


TEXT = {"type": "string"}
TOOLS = [
    schema("excel_list_files", "Liệt kê file XLSX trong whitelist.", {}, []),
    schema("excel_list_sheets", "Liệt kê sheet của XLSX.", {"path": TEXT}, ["path"]),
    schema("excel_read", "Đọc ô Excel, công thức trả biểu thức; tối đa 5000 ô.",
           {"path": TEXT, "sheet": TEXT, "cell_range": {"type": "string",
            "description": "Ví dụ A1:D20; mặc định A1:J20"}}, ["path", "sheet"]),
    schema("excel_summary", "Thống kê sheet bằng pandas; hàng 1 là header, dùng cache công thức.",
           {"path": TEXT, "sheet": TEXT}, ["path", "sheet"]),
    schema("excel_edit_cell", "Đề nghị sửa một ô. Phải chờ người dùng xác nhận UI. "
           "Text được ghi literal, không tạo công thức.",
           {"path": TEXT, "sheet": TEXT, "cell": TEXT,
            "value": {"type": ["string", "number", "boolean", "null"]}},
           ["path", "sheet", "cell", "value"]),
]

DOCUMENT_READ_SCHEMA = schema("document_read", "Đọc PDF/Word DOCX/TXT/HTML trong whitelist bằng Python. Đọc tiếp theo next_start đến hết; trả vị trí trang/đoạn thực.", {"path": TEXT, "start": {"type":"integer","minimum":0}, "limit":{"type":"integer","minimum":1,"maximum":8000}}, ["path"])

EXTRA_TOOLS = [
    ("office", schema("office_read", "Đọc text/bảng Word DOCX hoặc PowerPoint PPTX trong whitelist.", {"path": TEXT}, ["path"])),
    ("office", schema("office_create", "Tạo DOCX/PPTX mới sau khi người dùng duyệt. PPTX: mỗi slide là một khối, dòng đầu là tiêu đề, tách khối bằng newline---newline.", {"path": TEXT, "title": TEXT, "content": TEXT}, ["path", "title", "content"])),
    ("office", schema("word_replace", "Thay chuỗi xuất hiện đúng một lần trong đoạn/bảng DOCX, backup và duyệt. Định dạng đoạn được thay sẽ trở thành đồng nhất; header/footer chưa hỗ trợ.", {"path": TEXT, "search": TEXT, "replacement": TEXT}, ["path", "search", "replacement"])),
    ("web", schema("web_search", "Tìm web, trả tiêu đề/snippet/URL nguồn; cần Internet.", {"query": TEXT}, ["query"])),
    ("web", schema("web_read", "Đọc text trang web công khai để trả lời kèm URL nguồn.", {"url": TEXT}, ["url"])),
    ("files", schema("file_list", "Liệt kê thư mục whitelist, tối đa 100 mục.", {"path": TEXT}, [])),
    ("files", schema("file_read", "Đọc file UTF-8 trong whitelist.", {"path": TEXT}, ["path"])),
    ("files", schema("file_write", "Đề nghị tạo/ghi file text, bắt buộc duyệt preview trước ghi.",
                     {"path": TEXT, "content": TEXT}, ["path", "content"])),
    ("files", schema("file_edit", "Thay chuỗi xuất hiện đúng một lần; backup và duyệt trước sửa.",
                     {"path": TEXT, "search": TEXT, "replacement": TEXT}, ["path", "search", "replacement"])),
    ("files", schema("file_move", "Di chuyển file trong whitelist; đích chưa tồn tại; cần duyệt.",
                     {"path": TEXT, "destination": TEXT}, ["path", "destination"])),
    ("files", schema("file_delete", "Xóa một file sau backup; bắt buộc người dùng duyệt.", {"path": TEXT}, ["path"])),
    ("python", schema("python_run", "Chạy Python trong Docker cách ly với pandas, openpyxl, pypdf, python-docx, Pillow, imageio, imageio-ffmpeg và OpenCV. "
                      "Dùng Pillow/OpenCV để xử lý ảnh; imageio-ffmpeg để ghép ảnh thành MP4 cơ bản. Ghi file kết quả vào /output; sau khi người dùng duyệt chạy code, ứng dụng lưu tối đa 10 file (tổng 50 MiB) vào workspace/outputs. "
                      "Có thể sửa code sau lỗi và xin duyệt lại, tối đa 3 lần/lượt. Không truy cập host/mạng. files là đường dẫn whitelist, bản sao đọc tại /workspace/input/<tên file>.", {"code": TEXT, "files":{"type":"array","items":TEXT,"maxItems":8}}, ["code"])),
    ("python", schema("run_command", "Chạy lệnh shell Linux trong Docker với bản sao thư mục whitelist chỉ đọc. "
                      "Không phải cmd/PowerShell; cần duyệt; file tạo trong /tmp sẽ bị xóa.",
                      {"path": TEXT, "command": TEXT}, ["command"])),
    ("rag", schema("rag_index", "Đề nghị index TXT/MD/PDF/DOCX trong whitelist vào Chroma local; phải duyệt.",
                   {"path": TEXT}, ["path"])),
    ("rag", schema("rag_search", "Tra tài liệu đã index, trả nguồn/chunk để trích dẫn tiếng Việt.", {"query": TEXT}, ["query"])),
    ("media", schema("image_generate", "Tạo ảnh local bằng model đã chọn trong mục Tạo ảnh AI nâng cao (SD-Turbo nhanh hoặc SDXL-Turbo chất lượng cao), 512×512. Prompt tiếng Anh, dịch ý người dùng. "
                     "Cần duyệt trước tạo file PNG mới.", {"prompt": TEXT}, ["prompt"])),
    ("media", schema("video_generate", "Tạo MP4 6–9 giây từ 1–3 ảnh AI có zoom/pan. Đây là video từ ảnh, "
                     "không phải video diffusion. Prompts tiếng Anh. Cần duyệt trước tạo file.",
                     {"prompts": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}}, ["prompts"])),
    ("media_basic",schema("image_resize","Đổi kích thước ảnh trong whitelist bằng Pillow. Lưu ảnh PNG mới vào workspace/outputs, giữ nguyên ảnh nguồn và cần người dùng duyệt.",
                          {"path":TEXT,"width":{"type":"integer","minimum":64,"maximum":4096},"height":{"type":"integer","minimum":64,"maximum":4096}},["path","width","height"])),
    ("media_basic",schema("video_from_images","Ghép 1–8 ảnh trong whitelist thành MP4 1280×720 bằng imageio-ffmpeg; hiệu ứng zoom/pan nhẹ, 12 fps. Đây là slideshow, không phải video AI tạo cảnh mới. Lưu file mới trong workspace/outputs sau khi người dùng duyệt. Dùng file_list trước nếu cần tìm đường dẫn ảnh.",
                          {"image_paths":{"type":"array","items":TEXT,"minItems":1,"maxItems":8},"seconds_per_image":{"type":"integer","minimum":2,"maximum":8}},["image_paths","seconds_per_image"])),
]


EXTRA_TOOLS.append(('python',schema('python_search',
    'Viết công cụ tra cứu bằng Python standard library. Có web_search(query) và web_read(url) qua bridge. In kết quả và nguồn. Docker cách ly; tối đa4 yêu cầu web. Cần module web và python.',{'code':TEXT},['code'])))


EXTRA_TOOLS.extend([
    ('pdf_source', schema('pdf_source_open','Tải URL PDF HTTPS công khai tối đa 20 MiB vào thư mục được phép và mở Foxit Reader được phép; xin duyệt một lần. Trả text phần đầu và next_start. Dùng browser_search tìm URL thật trước; không đoán URL. app là đường dẫn EXE Foxit trong danh sách.',{'url':TEXT,'app':TEXT},['url','app'])),
    ('pdf_source', schema('pdf_read','Đọc tiếp PDF đã tải trong thư mục được phép, tối đa 8000 ký tự mỗi lần; cần duyệt. start là chuỗi số từ next_start. Không xem màn hình Foxit.',{'path':TEXT,'start':TEXT},['path'])),
    ('browser', schema('browser_search', 'Tự mở Chrome riêng, tìm Bing và đọc kết quả sau khi duyệt một lần. Không cần bật Tìm web riêng: quy trình này xin quyền truy cập mạng trong preview. Không đăng nhập, không tải file. Trả text và URL thực. Nếu có CAPTCHA, báo bị chặn và đề nghị URL nguồn; không yêu cầu giải CAPTCHA trong Chrome thường vì phiên riêng đã đóng.', {'path':TEXT,'query':TEXT}, ['path','query'])),
    ('browser', schema('browser_run', 'Thực hiện 1–12 bước Chrome sau khi duyệt toàn bộ quy trình. steps là chuỗi JSON mảng: [{"action":"navigate","url":"https://..."},{"action":"fill","selector":"...","text":"..."},{"action":"click","selector":"..."},{"action":"read"}]. Mỗi lần chạy có Chrome riêng mới, đóng khi xong; không tiếp tục phiên trước. Chỉ HTTPS công khai. Click có thể gửi biểu mẫu. Không nhập mật khẩu hoặc tải file.', {'path':TEXT,'steps':TEXT}, ['path','steps'])),
    ('windows', schema('windows_open', 'Mở ứng dụng Windows trong danh sách được phép, không shell/arguments. Bắt buộc người dùng duyệt.', {'path': TEXT}, ['path'])),
    ('windows', schema('windows_inspect', 'Đọc control UIA của phiên ứng dụng đã mở. Cần duyệt vì dữ liệu giao diện sẽ vào hội thoại. Không đọc ô mật khẩu.', {'session': TEXT}, ['session'])),
    ('windows', schema('windows_action', 'Thao tác một control từ lần windows_inspect gần nhất: click (UIA invoke), set_text (ô Edit), close (Window). Mỗi bước cần duyệt; đọc lại giao diện sau thao tác để xác minh. Không nhận tọa độ/phím/shell.', {'session': TEXT, 'control': TEXT, 'operation': {'type': 'string', 'enum': ['click', 'set_text', 'close']}, 'text': TEXT}, ['session', 'control', 'operation'])),
])

def validate_call(name, args, schemas=None):
    spec = next((t["function"] for t in (schemas if schemas is not None else TOOLS)
                 if t["function"]["name"] == name), None)
    if spec is None:
        raise ValueError(f"Tool không có trong registry: {name}")
    if not isinstance(args, dict):
        raise ValueError("Arguments phải là JSON object.")
    params = spec["parameters"]
    if set(args) - set(params["properties"]) or set(params["required"]) - set(args):
        raise ValueError("Thiếu tham số hoặc có tham số không được phép.")
    for key, value in args.items():
        if name == "calculate" and key == "values":
            if not isinstance(value,list) or not 1 <= len(value) <= 1000 or any(type(x) not in (int,float) for x in value):
                raise ValueError("values phải chứa 1–1000 số.")
        elif key == "prompts":
            if not isinstance(value, list) or not 1 <= len(value) <= 3 or not all(isinstance(x, str) for x in value):
                raise ValueError("prompts phải là danh sách 1–3 chuỗi.")
        elif key != "value" and not isinstance(value, str):
            if name=='video_from_images' and key=='image_paths':
                if not isinstance(value,list) or not 1<=len(value)<=8 or any(not isinstance(path,str) for path in value):
                    raise ValueError('image_paths phải có 1–8 đường dẫn ảnh.')
            elif name in {'image_resize','video_from_images'} and key in {'width','height','seconds_per_image'}:
                limits={'width':(64,4096),'height':(64,4096),'seconds_per_image':(2,8)}[key]
                if type(value) is not int or not limits[0]<=value<=limits[1]:raise ValueError(f'{key} ngoài giới hạn.')
            else:raise ValueError(f"{key} phải là chuỗi.")
