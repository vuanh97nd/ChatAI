# Chat AI — Hoàn thành giai đoạn 2–5

Giữ giao diện desktop Qt hiện tại, các nút hiện có, run.bat, model qwen2.5:7b và cơ chế xác nhận ghi/xóa/chạy lệnh. Bổ sung một hàng nhỏ dưới câu trả lời gồm 👍/👎 và tối đa 3 câu hỏi tiếp theo. Không sửa Worker, API đăng nhập hoặc bí mật server.

## Giai đoạn 2: tìm web
- Dùng Bing hiện có, không bắt buộc tải module mới. Có thể dùng trafilatura nếu môi trường đã có; thiếu thì bộ tách HTML chuẩn Python xử lý văn bản.
- Chỉ tìm/đọc web khi người dùng bật nút Tìm kiếm mạng và module web sẵn sàng. Không tự bật nút theo câu hỏi/phân loại; khi nút tắt, web_search, web_read và python_search đều bị chặn. Các lượt cũ không có quyền tìm kiếm rõ ràng cũng không được tự tiếp tục tra mạng.
- Tối đa 5 kết quả, thử đọc tối đa 5 trang để lấy 3 trang có văn bản. Có trạng thái tìm/đọc. Trang lỗi hoặc bị chặn được ghi rõ, không xem snippet là toàn văn. Không bảo đảm lúc nào cũng lấy đủ 3 trang.
- Tin tức/tài liệu có nguồn tên miền — tiêu đề — URL đầy đủ. Với thời tiết giữ lựa chọn không hiện link trừ khi được yêu cầu; vẫn cần dữ liệu tra thật.

## Giai đoạn 3: tính bằng Python
- Tool calculate dùng Decimal 40 chữ số, AST giới hạn; không eval/exec, không mạng hoặc file.
- Biểu thức số, sqrt/abs, thống kê, đơn vị mm/cm/m/km, g/kg/t, s/min/h, ml/l, C/F, chênh ngày ISO, giờ IANA.
- Chạy cả trong Chat nhanh khi model hỗ trợ tool calling. Không cần Docker cho calculate; tool Python chạy code tùy ý trước đây vẫn theo Docker/quyền hiện có.
- Không hiện đáp số model tự nhẩm khi chưa có kết quả calculate. Nếu model không gọi tool hoặc tool lỗi, báo chưa có kết quả, không bịa đáp số.
- Có trạng thái đang tính và vòng gọi công cụ như trước.

## Giai đoạn 4: ký ức dài hạn
- SQLite local theo tài khoản. Câu bắt đầu bằng “Hãy ghi nhớ: ...”, “Ghi nhớ: ...”, “Nhớ rằng ...” hoặc “Lưu vào bộ nhớ: ...” được lưu. Không tự lưu mọi câu chat hoặc suy đoán về người dùng.
- Không lưu nội dung có dấu hiệu mật khẩu/khóa truy cập. Đây là bộ lọc cơ bản, không phải công cụ nhận diện mọi loại bí mật.
- BGE-M3 chạy CPU khi module RAG sẵn sàng; thiếu embedding thì tìm bằng từ khóa. Ký ức được chọn theo độ liên quan, không đưa toàn bộ vào mỗi lượt.
- Trang Bộ nhớ hiện cả mục [Server] và [Máy này]. Mục server giữ API/KV hiện tại; mục local có thể sửa/xóa ngay trên trang đó, có xác nhận.
- Ký ức “Máy này” lưu bền trên máy, chưa tự đồng bộ lên server. Ký ức server được lấy/cache theo tài khoản; xóa trên server sẽ xóa bản sao ở lần đồng bộ thành công tiếp theo.
- Lịch sử trong thanh bên cũng lọc theo tài khoản; hội thoại cũ chưa gán tài khoản không tự nhận là của tài khoản đang đăng nhập, dữ liệu đó không bị xóa; nội dung không thuộc tài khoản đang đăng nhập không được mở từ danh sách.

## Giai đoạn 5: tài liệu, phản hồi, rà soát
- Chroma lưu vùng riêng từng tài khoản ở cùng thư mục dữ liệu local với SQLite. Bộ sưu tập mới dùng BGE-M3; không đọc chung index nomic cũ, không xóa index cũ.
- Câu hỏi tài liệu riêng tự tìm index đã có khi RAG sẵn sàng; tài liệu đính kèm được ưu tiên đọc trực tiếp. Lập chỉ mục mới vẫn cần xác nhận ở chế độ Công cụ.
- Chỉ nhận nguồn còn nằm trong whitelist, hash không đổi, cosine distance <=0.6. Ngưỡng là heuristic, không chứng minh nguồn đúng. Trả tên file/đoạn; PDF scan chưa có OCR.
- 👍/👎 áp dụng cho câu trả lời hoàn chỉnh mới nhất. 👎 có ô góp ý. SQLite lưu bản chụp câu hỏi/trả lời, model, phân loại và thời gian, theo tài khoản. Phản hồi không tự huấn luyện model.
- Nút gợi ý phụ thuộc loại câu trả lời và ngữ cảnh “vừa rồi”; bấm để điền câu hỏi, Enter gửi. Không thêm lượt model để sinh nút; trò chuyện ngắn không hiện gợi ý thừa.
- Câu khó hoặc cần chính xác cao có một lượt rà soát. Bản nháp được giữ ở nền, chỉ hiện bản đã rà soát. Chat thường bỏ qua. Rà soát lỗi thì giữ câu trả lời với thông báo chưa kiểm chứng xong, không nhận đã rà soát thành công. Đây là tự kiểm tra bằng cùng model, không thay thế kiểm chứng bên ngoài.
- Dữ liệu nguồn đưa vào model được rút gọn theo cấu trúc JSON hợp lệ; lịch sử và tài liệu gốc không bị cắt/sửa. Giới hạn ký tự là ước lượng, không phải tokenizer chính xác; tài liệu dài nên đặt câu hỏi cụ thể.

## File hoàn chỉnh đã cập nhật

File sửa:
- desktop_ui.py
- assistant/agent.py
- assistant/web.py
- assistant/modules.py
- assistant/rag.py
- assistant/capabilities.py
- assistant/tools.py
- assistant/storage.py

File mới:
- assistant/calculator.py
- assistant/memory.py
- assistant/quality.py
- assistant/feedback.py
- assistant/context.py
- tests/test_web_quality.py
- tests/test_calculator.py
- tests/test_memory.py
- tests/test_pipeline_quality.py
- evaluation/questions.json
- evaluation/score.py
- evaluation/README.md
- STAGES2_5.md

Các file đều là bản đầy đủ, không phải đoạn patch. requirements.txt cơ bản không đổi; Chroma/PDF/DOCX được cài qua module RAG có sẵn. Prompt và routing từ giai đoạn 1 tiếp tục được sử dụng.

## Cách chạy và tích hợp

1. Đóng Chat AI, đợi Drive đồng bộ toàn bộ file mới/sửa vào G:\My Drive\Dev\Chat-AI.
2. Mở Ollama và run.bat như trước. Không cần sửa work.js hoặc binding để dùng cập nhật local này.
3. Nếu cần embedding/RAG: trong Module chọn Bật/Tải RAG, xác nhận tải. Model cần là bge-m3; không tự tải khi chưa có xác nhận. Có thể tải thủ công bằng `ollama pull bge-m3` nếu muốn. Chưa có module vẫn dùng chat, Bing và calculate; ký ức dùng từ khóa.
4. Index nomic cũ cần lập chỉ mục lại ở chế độ Công cụ: “Lập chỉ mục file ... vào tài liệu riêng”; duyệt preview. File phải trong whitelist.
5. Gửi “Hãy ghi nhớ: tôi thích ví dụ Python”, mở chat mới rồi hỏi về cách lập trình để thử bộ nhớ. Trang Bộ nhớ cho xem/sửa/xóa ghi nhớ local và server.
6. Thử “Tính 0.1+0.2”, “Đổi 2,5 km sang m”, câu tin mới, câu tài liệu và 👍/👎.

Đã nối sẵn vào vòng lặp hiện tại: Agent.start đặt lại các cờ từng lượt; Agent.run phân loại → web/ký ức/RAG cần thiết → tool loop → rà soát có điều kiện → nguồn/gợi ý → lưu SQLite. desktop_ui tạo dịch vụ theo tài khoản và chuyển status/token qua Worker như trước. Tiếp tục sau xác nhận giữ nguyên trạng thái lượt, không tra/lưu lại vô điều kiện.

Kiểm thử tự động, chạy trong CMD tại thư mục dự án:
```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
Thay .venv nếu run.bat dùng tên môi trường khác.

Kết quả môi trường phát triển: 46 kiểm thử qua; compileall qua. Bao gồm streaming/tool, xác nhận/backup/whitelist cũ, web giả lập đọc 3 trang/lỗi, tính toán, không hiện số chưa tính, ký ức bền/cách ly/embedding giả lập, RAG hash/tài khoản, rà soát không lộ nháp/lỗi, feedback và bộ 30 câu.

Môi trường này không có Ollama, PySide6 hoặc Chroma thật; chưa mở giao diện Windows, chưa chạy Qwen/BGE trên RTX 3070, chưa kiểm tra Bing trực tiếp và chưa đo chất lượng/thời gian 30 câu bằng model thật. evaluation/README.md hướng dẫn chạy đánh giá trước/sau bằng dữ kiện tương đương, không có điểm chất lượng bịa.

Tài liệu API tham khảo:
- https://docs.ollama.com/capabilities/embeddings
- https://docs.trychroma.com/reference/python
- https://ollama.com/library/bge-m3
- https://ollama.com/library/qwen2.5:14b
