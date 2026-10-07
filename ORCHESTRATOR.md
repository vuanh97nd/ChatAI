# Chuyên gia phối hợp trong Chat AI

Bản cập nhật nguồn ngày 06/10/2026. Chat thường giữ AI người dùng đang chọn, không tự chuyển sang AI code. Các AI local hỗ trợ tool được cấp công cụ đọc/tính/Python theo module sẵn sàng, ngay trong chat thường. Chỉ mục **Chuyên gia** bật bộ điều phối. Các chế độ tạo ảnh/video sẵn có vẫn dùng công cụ tương ứng.

## Bố cục và cách dùng

- Thanh bên: **Trò chuyện**, **Chuyên gia**, lịch sử và các mục hiện có.
- Trong Chuyên gia, thanh nhỏ phía trên nội dung có **Tự động phối hợp / Chat chung / Lập trình / Đọc ảnh**, cạnh **Chi tiết xử lý**. Không mở cửa sổ chat mới.
- Gửi văn bản, ảnh hoặc tệp như trước. Trạng thái hiện theo bước đang thực hiện; nút dừng hiện có vẫn dùng được.
- **Hiểu sai ý? Chọn lại chuyên gia** đặt dưới vùng trả lời. Nút này điền lại câu hỏi và dữ liệu còn sẵn; người dùng bấm Gửi để chạy lại, tránh tự phát sinh yêu cầu mới.
- **Tìm kiếm mạng** là quyền riêng. Trong Chuyên gia, bấm nút chỉ bật/tắt web, không rời chế độ Chuyên gia. Mặc định tắt. Khi tắt, không tìm qua Bing, web_read hoặc python_search; sandbox Python không có mạng.
- Chuyên gia dùng Ollama local. Nếu đang chọn Cloudflare AI, ứng dụng yêu cầu chọn AI trên máy. Chat Cloudflare thường giữ luồng hiện có.

## Điểm vào và cấu hình

Điểm vào là `Agent.start(..., expert_mode=True, expert_override=None)` rồi `Agent.run(state)`. UI truyền `ui_mode=5` và `web_search_requested` từ nút thực tế. Luồng chat thường không truyền expert_mode.

`experts.yaml` chứa tên, role, model, fallback_models, mission, temperature, when. File mặc định viết bằng JSON hợp lệ theo YAML 1.2, nên chạy cả khi PyYAML chưa có; bộ cài có bổ sung PyYAML để đọc YAML thông thường. Sửa file rồi gửi yêu cầu mới để nạp lại. File cấu hình lỗi không làm mất hội thoại: có thông báo và dùng luồng dự phòng.

Model mặc định: Qwen2.5 7B tổng hợp, Qwen2.5-Coder 7B lập trình, Gemma3 4B vision (đã có trong danh mục app), Qwen2.5 3B lập kế hoạch nếu đã tải. Không tự kéo model mới. Nếu chưa có planner nhỏ, dùng model phù hợp đã có. Chuyên gia code chưa tải thì AI chung làm dự phòng và nêu giới hạn. Muốn đổi vision, chọn model vision thực sự được Ollama hỗ trợ và vừa máy trong cấu hình; việc model vừa 8GB phụ thuộc quantization, context và ảnh đầu vào.

Custom expert kiểu llm được kích hoạt bằng `when`, ví dụ `need_code: true`, `has_images: true`, hoặc được planner yêu cầu theo tên. Nó nhận câu hỏi, bộ nhớ, OCR và bằng chứng; kết quả đi vào ngữ cảnh trước bước tổng hợp. Tool mới cần triển khai API và đăng ký công cụ tương ứng, không thể tạo khả năng thực thi mới chỉ bằng YAML. Embedding hiện dùng bge-m3 trong bộ nhớ/RAG; đổi embedding cần di trú/tạo lại index tương thích, không chỉ đổi tên cấu hình.

## Chuyển giao và giới hạn thật

Ảnh → JSON OCR giữ nguyên code, lỗi, tên file, bảng và vùng không rõ → code hoặc AI chung. Vision không nhìn rõ phải ghi `[KHÔNG ĐỌC RÕ]`; không có vision hoặc gọi lỗi thì báo chưa đọc được ảnh. JSON được kiểm tra kiểu cả code/table; không coi OCR là đã kiểm chứng độc lập.

File/RAG/web → đọc nguồn → shared context → code hoặc công cụ tính → tổng hợp. Bộ nhớ vẫn lọc theo tài khoản. Khi RAG cần toàn văn, đọc lại file qua whitelist và kiểm tra hash; chunk retrieval không tự được coi là toàn văn.

Tạo ảnh/video → AI chung cải thiện prompt → công cụ đã có, theo xác nhận hiện tại. Video hiện là MP4 chuyển động từ ảnh (zoom/pan), chưa phải video diffusion. Chưa có module thì ứng dụng dùng bước hỏi tải hiện có; không gói sẵn thư viện media nặng.

Code Python có thể đưa vào `python_run` nếu sandbox được bật, đoạn code đầy đủ và không có chỗ OCR chưa rõ. Docker cô lập, không mạng, không GPU, giới hạn RAM/thời gian; không chạy trực tiếp trên Windows host. Quyền auto_python hoặc hộp xác nhận giữ theo cấu hình hiện tại. Thiếu Docker/module, bị từ chối hoặc chưa có code chạy được thì báo **chưa chạy thử**. Kiểm thử sandbox thành công cũng không chứng minh toàn bộ chương trình đúng trên Windows. Các lần model tự sửa được giới hạn bởi vòng tool và số lần chạy hiện có.

Shared context lưu câu gốc, 10 lượt gần nhất theo ngân sách, ký ức liên quan, plan, OCR, kết quả tool, nguồn, giả định, phần chưa làm được, trace và thời gian model. Chi tiết xử lý hiển thị dữ liệu này. Checklist cuối ghi trạng thái từng bước; `semantic_verified=false`: không giả định rằng checklist tự chứng minh mọi yêu cầu đúng về ngữ nghĩa.

Chuyên gia code gặp lỗi có một lần thử AI chung dự phòng. Vision lỗi không dùng AI text để đoán ảnh. SDK có timeout kết nối/đọc hiện tại 180 giây; nút dừng xử lý theo cơ chế hiện có ở ranh giới sự kiện, không hứa ngắt ngay một lời gọi đang chờ. Cảnh báo luồng chậm dựa trên số đo trả về sau lời gọi. Có thể xem load_seconds/elapsed_seconds từng lời gọi trong Chi tiết.

## VRAM

SerialClient chạy tuần tự, unload model trước khi đổi; các lời gọi liên tiếp cùng model không reload. Embedding dùng CPU. Khi ứng dụng tự khởi động Ollama, đặt `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`; Ollama đã chạy trước đó không tự nhận biến môi trường mới. Cần thoát Ollama và mở lại nếu muốn áp dụng cấu hình daemon. App vẫn chủ động unload khi chuyển model. Không kiểm soát tiến trình Ollama do ứng dụng khác gọi cùng lúc, hoặc VRAM do phần mềm tạo ảnh khác sử dụng.

Tài liệu Ollama: https://docs.ollama.com/faq

## Kiểm thử

Từ thư mục dự án:

```bat
runtime\python\python.exe -m unittest discover -s tests -q
```

Nếu đang phát triển với venv, thay bằng `.venv\Scripts\python.exe`. Bộ `tests/orchestrator_cases.json` có 20 tình huống để chạy thủ công trên ảnh/file thật. `tests/test_orchestrator.py` kiểm tra cơ chế bằng client giả: kế hoạch, bàn giao, giữ OCR, quyền web, unload, bộ nhớ, thiếu media, sandbox và câu trả lời duy nhất. Nó không đo độ chính xác Qwen/Gemma, tốc độ GPU hoặc giao diện Windows.

Để đánh giá thật, dùng từng câu trong bộ 20 tình huống với ảnh/file biết trước nội dung. Chấm 0–2 cho: đủ phần yêu cầu; OCR/dữ liệu giữ nguyên; kết quả code/tính có công cụ chứng minh; nguồn đúng; giới hạn và quyền được tuân thủ. Đạt tối thiểu 8/10 và không có lỗi nghiêm trọng: bịa ảnh, nhận chạy thử giả, tìm web khi tắt hoặc trộn tài khoản. So sánh cùng model, quantization, num_ctx và file đầu vào trước/sau.

## Chạy bản cập nhật

Đồng bộ xong các file nguồn trong thư mục Chat-AI, đóng app rồi mở `run.bat` như trước. Người dùng chạy EXE đã đóng gói phải build lại bộ cài bằng quy trình `WINDOWS_BUILD.md`; bản cập nhật này chưa tạo EXE mới. Inno đã đưa experts.yaml/glossary.json vào bộ cài và giữ file người dùng tùy chỉnh khi nâng cấp. Các file hoàn chỉnh, mới/sửa có trong `CHANGES_EXPERTS.md`.

## Cập nhật quyền Python và trả lời tự nhiên

Bỏ thẻ hướng dẫn, ví dụ và khuôn bố cục khỏi ngữ cảnh trả lời. Thêm document_read đọc PDF/DOCX theo offset và vị trí trang/đoạn. python_run nhận files thuộc whitelist, chụp bản sao kiểm hash tại /workspace/input/<tên file>. Bật auto_python theo yêu cầu. Module Python dùng image chat-ai-python-tools:1, có pandas/openpyxl/pypdf/python-docx. Cần Docker Desktop và tải/cài lại module Python một lần để build image mới; thao tác này có tải thư viện. Code tự chạy/sửa trong giới hạn hiện có, không có quyền ghi thẳng host hay lách nút web. Sandbox không mạng; tìm kiếm dùng python_search bridge khi nút web bật. Chưa chạy kiểm thử sau những thay đổi mới này theo yêu cầu người dùng.

Điều chỉnh cuối: prompt trả lời chỉ còn tên Chat AI và tiếng Việt. Không nạp thẻ kinh nghiệm/few-shot, không rà soát viết lại theo checklist, không áp thứ tự kết luận/giải thích hoặc cách hỏi lại. Quyền và xác nhận công cụ vẫn do mã nguồn kiểm soát. Chưa chạy lại kiểm thử theo yêu cầu.
