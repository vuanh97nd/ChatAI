WRITES = {"excel_edit_cell", "excel_create_from_template", "template_fill", "file_write", "file_edit", "file_move", "file_delete", "image_resize", "video_from_images",
          "python_run", "python_search", "run_command", "rag_index", "image_generate", "video_generate", "office_create", "word_replace", "windows_open", "windows_inspect", "windows_action", "browser_search", "browser_run"}
WRITES.update({'pdf_source_open','pdf_read'})
WRITES.add('windows_list_apps')
WRITES.add('geoslope_create')

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
    schema("excel_create_from_template",
           "Tạo file XLSX mới từ file mẫu (template) rồi điền dữ liệu vào nhiều ô cùng lúc. "
           "Dùng khi người dùng có form/biểu mẫu sẵn và muốn điền nội dung mới. "
           "template: đường dẫn file .xlsx mẫu trong whitelist. "
           "output_name: tên file mới (chỉ tên, không đường dẫn; sẽ lưu cùng thư mục template). "
           "fills là chuỗi JSON mảng tối đa 500 phần tử: "
           '[{"sheet":"Sheet1","cell":"B3","value":"Nội dung"},{"sheet":"Sheet1","cell":"C4","value":123}]. '
           "value có thể là string, số, boolean hoặc null (xóa ô). "
           "Text ghi literal, không tạo công thức. Công thức trong template được giữ nguyên. "
           "Hỏi người dùng xem template nào nếu chưa rõ.",
           {"template": TEXT, "output_name": TEXT, "fills": TEXT},
           ["template", "output_name", "fills"]),
]

DOCUMENT_READ_SCHEMA = schema("document_read", "Đọc PDF/Word DOCX/TXT/HTML trong whitelist bằng Python. Đọc tiếp theo next_start đến hết; trả vị trí trang/đoạn thực.", {"path": TEXT, "start": {"type":"integer","minimum":0}, "limit":{"type":"integer","minimum":1,"maximum":8000}}, ["path"])

EXTRA_TOOLS = [
    ("template", schema("template_scan", "Đọc file .docx mẫu và liệt kê các placeholder {{tên}} cần điền.",
                        {"path": TEXT}, ["path"])),
    ("template", schema("template_fill",
        'Điền dữ liệu vào file Word mẫu (.docx) và tạo file mới. '
        'Template dùng cú pháp {{tên_trường}} trong đoạn văn và ô bảng. '
        'Dùng template_scan trước để biết các placeholder. '
        'values là chuỗi JSON: {"project_name":"Nhà dân","date":"2024",...}. '
        'Không sửa template gốc; luôn tạo file mới.',
        {'template': TEXT, 'output_name': TEXT, 'values': TEXT},
        ['template', 'output_name', 'values'])),
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
    ('windows',schema('windows_list_apps','Liệt kê app được phép hoặc ứng dụng đã cài khi quyền mở mọi app bật. query lọc theo tên/đường dẫn. Dùng để tìm EXE thật trước khi mở, không đoán đường dẫn. Cần duyệt chia sẻ danh sách với AI.',{'query':TEXT},[])),
    ('pdf_source', schema('pdf_source_open','Tải URL PDF HTTPS công khai tối đa 20 MiB vào thư mục được phép và mở Foxit PDF Reader hoặc Foxit PDF Editor được phép; xin duyệt một lần. Trả text phần đầu và next_start. Dùng browser_search tìm URL thật trước; không đoán URL. app là đường dẫn EXE Foxit trong danh sách.',{'url':TEXT,'app':TEXT},['url','app'])),
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

WRITES.add('word_create_open')
EXTRA_TOOLS.append(('word_app',schema('word_create_open','Soạn nội dung rồi tạo DOCX mới trong thư mục được phép và mở bằng Word. Dùng công cụ này khi người dùng yêu cầu mở Word và viết bài; không nhập vùng soạn thảo qua UIA. app phải là WINWORD.EXE đã tìm bằng windows_list_apps. content là nội dung đầy đủ, tối đa 30000 ký tự.',{'app':TEXT,'title':TEXT,'content':TEXT},['app','content'])))

WRITES.add('cad_create_open')
EXTRA_TOOLS.append(('cad_app',schema('cad_create_open',
'Tạo bản vẽ DXF 2D mới và mở AutoCAD. Tìm acad.exe/acadlt.exe bằng windows_list_apps. units: mm/cm/m/inch. '
'entities là chuỗi JSON mảng hình, tối đa 500 phần tử. Các loại hỗ trợ:\n'
'• {"type":"line","start":[x,y],"end":[x,y],"layer":"TÊN"}\n'
'• {"type":"circle","center":[x,y],"radius":r,"layer":"TÊN"}\n'
'• {"type":"rectangle","origin":[x,y],"width":w,"height":h,"layer":"TÊN"}\n'
'• {"type":"polyline","points":[[x,y],...],"closed":true/false,"layer":"TÊN"} — biên lớp đất, tường chắn\n'
'• {"type":"hatch","boundary":[[x,y],...],"pattern":"ANSI31","scale":1.0,"angle":0,"layer":"TÊN"} — ký hiệu đất\n'
'  pattern hợp lệ: ANSI31(sét), ANSI32, ANSI33, ANSI34, AR-SAND(cát), AR-CONC(bê tông), EARTH(đất lấp), GRASS(cỏ), GRAVEL(cuội), MUDST(bùn), DOTS, SOLID, CROSS, STEEL, SWAMP\n'
'• {"type":"text","insert":[x,y],"content":"Văn bản","height":h,"rotation":0,"halign":"LEFT/CENTER/RIGHT","valign":"BASELINE/BOTTOM/MIDDLE/TOP","layer":"TÊN"}\n'
'• {"type":"dim_linear","start":[x,y],"end":[x,y],"dimline":[x,y],"text_override":"","layer":"TÊN"} — kích thước\n'
'layers (tùy chọn) là chuỗi JSON mảng: [{"name":"ĐẤT_1","color":2,"linetype":"CONTINUOUS"}] — màu ACI 1–256, linetype: CONTINUOUS/DASHED/DOTTED/CENTER/PHANTOM/HIDDEN.\n'
'styles (tùy chọn) là chuỗi JSON mảng khai báo text style: [{"name":"VN_SAN","font":".VnArial","height":0,"width_factor":1.0}].\n'
'  Font Unicode (TTF): .VnArial, .VnTimes, Arial, Times New Roman — text giữ nguyên Unicode.\n'
'  Font TCVN3 (SHX): VNTIMES.SHX, VNARIAL.SHX, vnet.shx, vnhelveti.shx — text tự động convert sang TCVN3.\n'
'  Thêm "style":"VN_SAN" vào entity text để áp dụng style đã khai báo.\n'
'Gợi ý mặt cắt địa kỹ thuật: polyline biên lớp đất, hatch ký hiệu, text nhãn cao độ, dim_linear chiều sâu.\n'
'Hỏi kích thước/đơn vị nếu thiếu; không tự đoán. Không sửa DWG/bản vẽ đang mở, không chạy script CAD.',
{'app':TEXT,'units':TEXT,'entities':TEXT,'layers':TEXT,'styles':TEXT},['app','units','entities'])))

WRITES.add('cad3d_create_open')
EXTRA_TOOLS.append(('cad3d_app',schema('cad3d_create_open','Tạo DXF 3D dạng lưới kín và mở AutoCAD acad.exe, không hỗ trợ LT. Không phải ACIS solid/DWG, chưa bo cạnh. units: mm/cm/m/inch. shape là chuỗi JSON: {"type":"box","origin":[0,0,0],"width":100,"depth":80,"height":30}; hoặc {"type":"cylinder","origin":[0,0,0],"radius":50,"height":20}; hoặc {"type":"flange","origin":[0,0,0],"outer_radius":120,"inner_radius":40,"height":20,"hole_radius":9,"hole_count":8,"bolt_radius":90}. Tâm trụ/mặt bích là origin ở đáy; lỗ bu-lông chia đều, lỗ đầu trên hướng +X; các lỗ xuyên chiều cao. Hỏi thông số/đơn vị thiếu, không đoán; báo rõ không hỗ trợ bo cạnh. Đường tròn xấp xỉ 64 cạnh.',{'app':TEXT,'units':TEXT,'shape':TEXT},['app','units','shape'])))
WRITES.add('geoslope_create')
EXTRA_TOOLS.append(('geoslope_app', schema('geoslope_create',
    'Tạo file GeoSlope/W (.gsz) phân tích ổn định mái dốc. '
    'project_name: tên dự án (1–100 ký tự). '
    'problem: chuỗi JSON mô tả bài toán gồm slope (height, angle, crest_width, toe_width), '
    'materials (name, cohesion, phi, unit_weight, model), layers (material_index, top_y, bottom_y), '
    'method (Bishop/Morgenstern-Price/Spencer/Janbu/Ordinary), water_table (null hoặc cao trình). '
    'Lưu file .gsz vào thư mục whitelist; mở bằng GeoStudio để chạy phân tích. '
    'auto_open: true để tự động mở file .gsz bằng GeoStudio sau khi tạo.',
    {'project_name': TEXT, 'problem': TEXT, 'auto_open': {'type': 'boolean'}},
    ['project_name', 'problem'])))

EXTRA_TOOLS.append(('soilfirm_app', schema('soilfirm_read',
    'Đọc file dự án SoilFirm Pro (.json, format saspro-python-1) và trả về dữ liệu địa chất, '
    'thông số thiết kế và kết quả tính (nếu có). '
    'Dùng để lấy số liệu địa kỹ thuật chuẩn bị lập báo cáo hoặc phân tích. '
    'path: đường dẫn đầy đủ file dự án SoilFirm Pro trong whitelist. '
    'mode: "summary" (tóm tắt nhanh, mặc định) hoặc "full" (toàn bộ trường dữ liệu).',
    {'path': TEXT, 'mode': {'type': 'string', 'enum': ['summary', 'full']}},
    ['path'])))

WRITES.add('soilfirm_create')
EXTRA_TOOLS.append(('soilfirm_app', schema('soilfirm_create',
    'Tạo file dự án SoilFirm Pro từ dữ liệu địa chất AI đọc từ Excel hoặc nhập tay. '
    'Dùng sau khi đọc Excel bằng excel_read/excel_summary và ánh xạ cột → chỉ tiêu đất. '
    'project_name: tên công trình/dự án. '
    'output_name: tên file kết quả (ví dụ KM32-BH1.json). '
    'soils: chuỗi JSON mảng lớp đất, mỗi lớp gồm: '
    'name (tên lớp), thickness (m), gamma (kN/m³), e0, cc, cs, pc (kPa), '
    'cv_constant (cm²/s, tùy chọn), cohesion_c (kPa), friction_phi (°), '
    'phi_cu_effective (°, tùy chọn), spt_n, category (Đất dính/Đất rời/Đất hữu cơ/Đá), '
    'state (Quá cố kết/Cố kết thường/Chưa cố kết xong). '
    'Ví dụ soils: [{"name":"Lớp 1 – Bùn sét","thickness":3.5,"gamma":15.2,'
    '"e0":1.35,"cc":0.42,"cs":0.05,"pc":25,"cohesion_c":8.5,"friction_phi":6.2,'
    '"category":"Đất dính","state":"Chưa cố kết xong"}]. '
    'Các trường tùy chọn để null nếu không có số liệu; không tự bịa số.',
    {'project_name': TEXT, 'output_name': TEXT, 'soils': TEXT,
     'design_stage': TEXT, 'borehole_name': TEXT,
     'h_design': {'type': 'number'}, 'gamma_fill': {'type': 'number'},
     'water_depth': {'type': 'number'}, 'ground_elevation': {'type': 'number'}},
    ['project_name', 'output_name', 'soils'])))

WRITES.add('borehole_dxf')
EXTRA_TOOLS.append(('borehole_dxf', schema('borehole_dxf',
    'Vẽ trụ địa chất (borehole log) dạng DXF và mở AutoCAD. '
    'Tạo bản vẽ chuẩn với cột hatch lớp đất, cột số liệu γ/e₀/Cc/c/φ/N-SPT, '
    'đường mực nước ngầm. Font .VnArial Unicode. '
    'app: đường dẫn acad.exe đã tìm bằng windows_list_apps. '
    'borehole_name: mã lỗ khoan (VD: BH-1). '
    'ground_elevation: cao độ mặt đất (m). '
    'water_depth: chiều sâu mực nước ngầm từ mặt đất (m, 0 nếu không có). '
    'soils: chuỗi JSON mảng lớp đất, mỗi lớp: '
    '{"name":"Sét xám","thickness":3.5,"gamma":15.2,"e0":1.35,'
    '"cc":0.42,"cohesion_c":8.5,"friction_phi":6.2,"spt_n":4,'
    '"category":"Đất dính"}. '
    'Dùng soilfirm_read hoặc excel_read để lấy số liệu trước.',
    {'app': TEXT, 'borehole_name': TEXT, 'ground_elevation': {'type': 'number'},
     'water_depth': {'type': 'number'}, 'soils': TEXT},
    ['app', 'borehole_name', 'soils'])))

WRITES.add('plaxis_generate_script')
EXTRA_TOOLS.append(('plaxis_app', schema('plaxis_generate_script',
    'Tạo script Python cho Plaxis 2D/3D để phân tích địa kỹ thuật. '
    'Hỗ trợ: slope_stability (ổn định mái dốc, Bishop/Fellenius), '
    'foundation_settlement (lún móng nông), retaining_wall (tường chắn đất). '
    'version: "2d" hoặc "3d". '
    'problem: chuỗi JSON mô tả bài toán, ví dụ: '
    '{"type":"slope_stability","slope_angle":30,"slope_height":5,'
    '"analysis":"Bishop","soil_layers":[{"name":"Cat","E":10000,"nu":0.3,'
    '"gamma":18,"c":5,"phi":30,"thickness":5}]}. '
    'Script sinh ra cần mở trong Plaxis bằng File > Run Script. '
    'auto_run: true để tự động kết nối Plaxis đang mở và chạy script (cần plxscripting + Plaxis Remote Scripting Server đang bật).',
    {'project_name': TEXT, 'version': TEXT, 'problem': TEXT, 'auto_run': {'type': 'boolean'}},
    ['project_name', 'version', 'problem'])))

WRITES.add('plaxis_run_problem')
EXTRA_TOOLS.append(('plaxis_remote', schema('plaxis_run_problem',
    'Kết nối trực tiếp Plaxis 2D/3D qua Remote Scripting Server (ưu tiên), '
    'tự động chuyển sang UI Control nếu server chưa bật. '
    'Trả về kết quả số: lún lớn nhất (mm), chuyển vị ngang (mm), hệ số an toàn (SF), kết quả từng giai đoạn. '
    'Remote Scripting cần: pip install plxscripting + Expert > Configure remote scripting server > Start. '
    'UI Control fallback cần: Plaxis đang mở (Windows) + pywinauto đã cài; '
    'cung cấp plaxis_exe để tự khởi động Plaxis nếu chưa mở. '
    'version: "2d" hoặc "3d". '
    'problem: JSON mô tả bài toán: '
    '{"type":"excavation_pit","excavation_depth":6,"excavation_width":8,"wall_thickness":0.5,'
    '"embedment_depth":2,"soil_layers":[{"name":"Cat","E":20000,"nu":0.3,"gamma":18.5,"c":5,"phi":28,"thickness":8}]}.',
    {'project_name': TEXT, 'version': TEXT, 'problem': TEXT, 'plaxis_exe': TEXT},
    ['project_name', 'version', 'problem'])))

WRITES.add('plaxis_ui_run')
EXTRA_TOOLS.append(('plaxis_ui_control', schema('plaxis_ui_run',
    'Điều khiển UI Plaxis 2D/3D trực tiếp (File > Run Script) để thực thi script phân tích địa kỹ thuật. '
    'Dùng khi Remote Scripting Server không khả dụng. Chỉ hoạt động trên Windows với pywinauto đã cài. '
    'Tự động chụp ảnh màn hình kết quả sau khi tính toán xong. '
    'Cung cấp plaxis_exe nếu muốn tự khởi động Plaxis (ví dụ: C:\\\\Program Files\\\\Plaxis\\\\PLAXIS2D.exe). '
    'version: "2d" hoặc "3d". '
    'problem: chuỗi JSON mô tả bài toán (cùng định dạng plaxis_run_problem).',
    {'project_name': TEXT, 'version': TEXT, 'problem': TEXT, 'plaxis_exe': TEXT},
    ['project_name', 'version', 'problem'])))

WRITES.add('road_analyze')
EXTRA_TOOLS.append(('road_pipeline', schema('road_analyze',
    'Đọc DXF trắc dọc + mặt cắt ngang (tuỳ chọn) + danh sách lỗ khoan JSON → phân đoạn địa kỹ thuật → điền mẫu THSH. '
    'profile_dxf: đường dẫn file DXF trắc dọc (layers Prf-acc/Prf-ege/Prf-fge/XSTA). '
    'mcn_dxf: đường dẫn file DXF mặt cắt ngang (tuỳ chọn, layers XSTA/XGRIDFGT/XGRIDT/XFG). '
    'boreholes: chuỗi JSON mảng hố khoan, mỗi hố gồm name, station (m), ground_elev, hdy (chiều sâu đất yếu), '
    'b_nen (m), layers (mảng {code, thickness, Cc, Cs, e0, Pc, Su, E, nu, p0}). '
    'template_xlsx: đường dẫn file Excel mẫu có sheet THSH. '
    'output_xlsx: đường dẫn file kết quả sẽ tạo. '
    'segment_length: độ dài đoạn tính toán (m, mặc định 200). '
    'Trả về danh sách đoạn với phương án xử lý, lún và Fs; ghi vào THSH sau khi duyệt.',
    {'profile_dxf': TEXT, 'mcn_dxf': TEXT, 'boreholes': TEXT, 'template_xlsx': TEXT,
     'output_xlsx': TEXT, 'segment_length': {'type': 'number'}},
    ['profile_dxf', 'template_xlsx', 'output_xlsx'])))

WRITES.add('road_verify')
EXTRA_TOOLS.append(('road_pipeline', schema('road_verify',
    'Xác nhận lại và điền lại THSH với thông số xử lý người dùng điều chỉnh. '
    'segments: chuỗi JSON mảng đoạn (từ road_analyze) có thể có thêm treatment_override. '
    'template_xlsx: đường dẫn file mẫu THSH. '
    'output_xlsx: đường dẫn file kết quả. '
    'Tính lại lún và Fs rồi ghi vào THSH sau khi duyệt.',
    {'segments': TEXT, 'template_xlsx': TEXT, 'output_xlsx': TEXT},
    ['segments', 'template_xlsx', 'output_xlsx'])))

WRITES.add('cad_tracdoc_xldy')
EXTRA_TOOLS.append(('cad_drawing', schema('cad_tracdoc_xldy',
    'Vẽ bản vẽ trắc dọc xử lý đất yếu (XLDY) dạng DXF từ danh sách đoạn THSH. '
    'Xuất file DXF với bảng số liệu 9 hàng (Lý trình, Tên cọc, Cao độ TN/TK, Htk…) '
    'và mặt cắt profile có vùng PVD/CDM, đường thiết kế, đường tự nhiên. '
    'segments_json: mảng JSON các đoạn (từ road_analyze/road_verify). '
    'output_dxf: đường dẫn file DXF kết quả.',
    {'segments_json': TEXT, 'output_dxf': TEXT},
    ['segments_json', 'output_dxf'])))

WRITES.add('klxldy_write')
EXTRA_TOOLS.append(('klxldy', schema('klxldy_write',
    'Lập bảng khối lượng xử lý đất yếu (XLDY) ra file Excel theo form XLDY_THU_THIEM. '
    'Tự động tính số lượng cọc CDM, bấc thấm/giếng cát, khối đào thay, cọc tre/cừ tràm, '
    'vải địa kỹ thuật, bàn đo lún theo từng đoạn. '
    'segments_json: mảng JSON đoạn (từ road_analyze/road_verify). '
    'output_xlsx: đường dẫn file kết quả. '
    'project_name: tên dự án (tuỳ chọn).',
    {'segments_json': TEXT, 'output_xlsx': TEXT, 'project_name': TEXT},
    ['segments_json', 'output_xlsx'])))

WRITES.add('tm_xldy_write')
EXTRA_TOOLS.append(('tm_xldy', schema('tm_xldy_write',
    'Soạn thuyết minh tính toán xử lý đất yếu (XLDY) ra file Word (.docx) theo form TMXLDY. '
    'Gồm 5 chương: Giới thiệu, Cơ sở tính toán, Lý thuyết công thức, Kết quả tính toán, Quan trắc. '
    'Đúng cả nội dung chữ lẫn bảng số liệu theo mẫu chuẩn. '
    'segments_json: mảng JSON đoạn. '
    'output_docx: đường dẫn file kết quả. '
    'project_name, sta_from, sta_to: thông tin dự án (tuỳ chọn). '
    'soil_params_json: mảng JSON chỉ tiêu đất [{"code","description","gamma","Su","e0","Cc","Cs","Cv","Pc"}] (tuỳ chọn).',
    {'segments_json': TEXT, 'output_docx': TEXT,
     'project_name': TEXT, 'sta_from': TEXT, 'sta_to': TEXT,
     'soil_params_json': TEXT},
    ['segments_json', 'output_docx'])))

WRITES.add('geoslope_write')
EXTRA_TOOLS.append(('geoslope_xldy', schema('geoslope_write',
    'Tạo file phân tích ổn định mái dốc GeoSlope SLOPE/W (.gsz) cho đoạn đường. '
    'Xây dựng mặt cắt ngang đắp (hdy), lớp đất yếu (htk), vùng xử lý (CDM/PVD/đào thay đất/cọc tre). '
    'Phân tích Bishop, bề mặt trượt GridAndRadius; Fs ≥ 1.2 (thi công), ≥ 1.4 (khai thác). '
    'output_gsz: đường dẫn file .gsz đầu ra. '
    'segments_json: JSON list các đoạn đường (từ road_analyze/road_verify). '
    'soil_params_json: JSON list thông số đất nền [{"role","name","gamma","cohesion","c_prime","phi_prime"}] (tuỳ chọn). '
    'project_name: tên dự án (tuỳ chọn). '
    'method: Bishop (mặc định)/Morgenstern-Price/Spencer/Janbu/Ordinary.',
    {'output_gsz': TEXT, 'segments_json': TEXT,
     'soil_params_json': TEXT, 'project_name': TEXT, 'method': TEXT},
    ['output_gsz', 'segments_json'])))

WRITES.add('cad_mcn_xldy')
EXTRA_TOOLS.append(('cad_drawing', schema('cad_mcn_xldy',
    'Vẽ bản vẽ mặt cắt ngang điển hình xử lý đất yếu (MCN XLDY) dạng DXF. '
    'Mỗi đoạn vẽ một mặt cắt ngang với nền đường, đất yếu, ký hiệu PVD hoặc CDM, kích thước Bn/Htk/hdy. '
    'segments_json: mảng JSON các đoạn (từ road_analyze/road_verify). '
    'output_dxf: đường dẫn file DXF kết quả.',
    {'segments_json': TEXT, 'output_dxf': TEXT},
    ['segments_json', 'output_dxf'])))
