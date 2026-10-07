# Cập nhật xử lý tài liệu tổng quát — 06/10/2026

Luồng: 10 lượt hội thoại → model nhẹ phân tích JSON → ưu tiên file/RAG gốc → 2–3 từ khóa chỉ chứa đối tượng → chấm điểm kết quả và kiểm lại nội dung → đọc HTML/PDF/DOCX → chia đoạn và tổng hợp phân cấp → trả lời linh hoạt → liệt kê nguồn được dẫn thật.

## File sửa

- `assistant/agent.py`: tích hợp vào chat local, tiến độ thực, ngữ cảnh và nguồn có điều kiện.
- `assistant/document_intent.py`: phân tích JSON bằng model nhẹ có sẵn, dự phòng, từ khóa và từ điển.
- `assistant/web.py`: đọc bản đầy đủ và file tải xuống; bỏ giới hạn cắt cũ khỏi luồng tài liệu, bỏ nhãn nguồn lặp.
- `assistant/prompts.py`: nguyên tắc linh hoạt và ví dụ tốt/xấu cho pháp luật, kỹ thuật, khoa học, doanh nghiệp.
- `assistant/answer_policy.py`: kiểm tra trạng thái đọc và mã nguồn, bỏ yêu cầu hỏi chi tiết máy móc.
- `assistant/routing.py`: dùng ngữ cảnh 10 lượt.
- `assistant/rag.py`: tìm bản gốc trong index, kiểm tra whitelist/hash rồi đọc lại.
- `assistant/cloud.py`, `assistant/support_ui.py`: model nhẹ trên server cho bước hiểu ý/tổng hợp; nhánh Cloudflare desktop dùng cùng bộ đọc Python và có tiến độ.
- `desktop_ui.py`: đọc đầy đủ PDF/DOCX đính kèm, giữ trang PDF, cho tài khoản đăng nhập dùng tài liệu với Cloudflare.
- `work.js`: endpoint model nhẹ `/api/document/model`, luồng tìm tài liệu chung trên server, prompt linh hoạt và nguồn có điều kiện.

## File mới

- `assistant/document_reader.py`: trích văn bản đầy đủ, theo trang PDF và đúng thứ tự bảng/đoạn DOCX.
- `assistant/document_pipeline.py`: ưu tiên nguồn người dùng, chấm điểm, map/reduce và footer nguồn.
- `glossary.json`: sửa cặp chữ viết tắt/nghĩa; nạp lại mỗi lượt, không cần sửa code.
- `document_reader_service.py`: bộ đọc phụ tùy chọn cho khách gọi Worker trực tiếp.
- `tests/document_cases.json`: 20 câu thuộc luật, kỹ thuật, y tế, tài chính, giáo dục, công nghệ; có viết tắt, nối tiếp, không tồn tại, đính kèm.
- `tests/test_document_pipeline.py`, `tests/test_worker_document.mjs`: kiểm thử hồi quy có dữ liệu giả lập.
- `tests/evaluate_documents.py`: chạy đánh giá thực với model Ollama và mạng.

## Áp dụng

Mã nguồn đã được cập nhật trực tiếp trong thư mục dự án. Đóng và mở lại ứng dụng để nạp file Python mới. Cần triển khai lại **work.js** lên Worker đang dùng để nhánh Cloudflare nhận endpoint mới; sửa file trên Drive không tự triển khai server.

Model nhẹ local mặc định `qwen2.5:3b` nếu đã có; nếu chưa có dùng model đang chọn, không tự tải. Server dùng biến `CHAT_AI_INTENT_MODEL`, mặc định `@cf/meta/llama-3.1-8b-instruct`. Có thể đặt model nhẹ phù hợp với tài khoản Cloudflare. Từ điển desktop lấy `glossary.json`; khách gọi Worker trực tiếp dùng biến `CHAT_AI_GLOSSARY_JSON` chứa cùng JSON.

Chat local và Cloudflare **trong ứng dụng desktop đã đăng nhập** đọc HTML/PDF/DOCX qua Python trên máy. Cloudflare nhận văn bản từng đoạn để tổng hợp. Web giữ nguyên quyền bật/tắt Tìm kiếm mạng. Tài liệu RAG giữ phân tách tài khoản và whitelist. Khách gọi Worker trực tiếp đọc HTML; PDF/DOCX cần service binding `DOCUMENT_READER` trỏ đến bộ đọc phụ (FastAPI + python-docx + pypdf, endpoint POST /read nhận bytes). Không cần service phụ cho nhánh desktop. Nếu thiếu bộ đọc/model/quyền mạng, phản hồi ghi đúng phần chưa đọc.

## Giới hạn được thể hiện trung thực

- PDF scan chưa có OCR: ghi các trang thiếu text; không nhận đã đọc toàn văn. Biểu đồ/hình không được coi là đã hiểu chỉ vì đọc được chữ.
- DOCX không có số trang đáng tin: dẫn mục/đoạn thay vì bịa số trang. HTML được đọc hết trang nhưng không tự coi trang giới thiệu là toàn văn tài liệu.
- Giới hạn tài liệu: 32 MiB, 4 triệu ký tự, 1000 đoạn. Vượt giới hạn hoặc lỗi map/reduce thì đánh dấu chưa hoàn tất. Không bỏ đoạn rồi nhận đã đọc hết.
- Tóm tắt phân cấp giữ thông tin theo yêu cầu, có thể mất chi tiết; yêu cầu trích dẫn/dịch dài cần kiểm tra với bản gốc. Không cam kết model không bao giờ bịa chỉ bằng prompt; đánh giá ngữ nghĩa vẫn cần kiểm tra thực.
- Câu hỏi tài liệu không tồn tại: báo chưa tìm được tài liệu phù hợp, phân biệt kiến thức chung với nội dung tài liệu chưa đọc.
- Nhánh Cloudflare tổng hợp dùng các lời gọi nhỏ riêng và hạn mức 120 lần/phút/tài khoản; chưa thay hạn mức lượt chat hiện có.

## Kiểm thử

Đã chạy thành công: 17 kiểm thử Python; Node kiểm tra 20 bộ từ khóa và các tình huống liên quan, đọc HTML dài, giữ nguyên bytes PDF, chặn URL private, không có kết quả. Kiểm tra cú pháp Python/JavaScript thành công.

Các kiểm thử dùng fixture/mock, không chứng minh chất lượng ngữ nghĩa của model thật. Chưa chạy 20 câu với Ollama/Cloudflare đang triển khai của bạn vì môi trường này không có phiên model/khóa dịch vụ của bạn.

Chạy từ thư mục dự án:

```bat
python -m unittest discover -s tests -v
node tests/test_worker_document.mjs
python -m tests.evaluate_documents --model qwen2.5:7b --output document-evaluation.json
```

Đánh giá thực: không hỏi thừa; không bịa mã/nghĩa/số liệu/điều khoản; từ khóa sạch; từng nguồn hỗ trợ ý được dẫn; tóm tắt dựa trên toàn bộ văn bản đọc được. Các kiểm tra tự động là bước hỗ trợ, không thay đánh giá các tiêu chí ngữ nghĩa.
