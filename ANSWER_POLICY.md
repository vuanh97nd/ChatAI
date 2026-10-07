# Cải thiện cách trả lời Chat AI

Giữ nguyên giao diện, model đang chọn và quyền web theo nút Tìm kiếm mạng. Không huấn luyện lại trọng số, không dùng API ChatGPT và không tải thêm model/thư viện.

File sửa hoàn chỉnh: assistant/prompts.py, assistant/agent.py, assistant/quality.py.
File mới hoàn chỉnh: assistant/answer_policy.py, tests/test_answer_policy.py, ANSWER_POLICY.md.

- Prompt tiếng Việt mới: 574 từ; kèm quy tắc công cụ tổng 697 từ.
- 20 tình huống hướng dẫn hành vi trong answer_policy.py. Chọn tối đa 2 mẫu theo phân loại và mức bằng chứng, tổng tối đa 900 ký tự. Không thêm lượt gọi model để chọn mẫu.
- evidence_record ghi quyền web, nguồn URL thật, mức độ truy xuất none/snippet/partial, công cụ thành công trong lượt hiện tại và trạng thái lưu ký ức. Không lấy thành công từ lượt trước để chứng minh thao tác hiện tại.
- Không suy ra full_document từ HTML/chunk RAG/attachment bị giới hạn. identity_verified mặc định false: chưa có bộ kiểm tra độc lập xác nhận mã/năm/cơ quan ban hành. Model phải đối chiếu dữ liệu, nêu giới hạn; không nhận đã xác minh độc lập.
- guard_answer kiểm tra một số mẫu câu khẳng định kiểm thử, sửa file, tìm mạng hoặc đọc toàn văn; thiếu kết quả tương ứng thì đổi câu sang thông báo giới hạn. Link Markdown không nằm trong tập nguồn truy xuất được đánh dấu chưa xác minh khi đang có nguồn thật. Giữ code block, lời dịch/sáng tác và một số câu trích dẫn/điều kiện.
- Streaming: trò chuyện và viết/dịch vẫn phát từng token. Các câu khác phát theo đoạn để kiểm tra mẫu khẳng định trước khi hiện; câu khó vẫn chỉ hiện bản sau rà soát như trước. Nếu model không xuống đoạn, phần văn bản đó xuất hiện khi kết thúc. Không thêm lượt rà soát cho chat thường.
- Lưu kết quả answer_checks cùng lịch sử và ghi audit các mẫu đã bị chặn; không ghi thêm toàn bộ tài liệu vào log guard.

Giới hạn: bộ kiểm tra là heuristic với những mẫu câu cụ thể, không hiểu mọi cách diễn đạt, không chứng minh mọi con số/kiến thức đúng, không kiểm chứng độc lập nội dung từng kết luận hoặc đúng tài liệu từ một mã tiêu chuẩn. Kiểm tra test stdout cũng chỉ là dấu hiệu kết quả tool, không chứng minh bộ test bao phủ đầy đủ. Cần nguồn thực và đánh giá bằng model thật; không gọi hệ thống này là AI đã tự học.

Đợi Drive đồng bộ, đóng Chat AI rồi chạy run.bat như trước. Không cập nhật work.js cho thay đổi này.

Kiểm thử trong CMD từ thư mục dự án:
```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
53 kiểm thử qua và compileall qua trong môi trường phát triển. Chưa chạy giao diện Windows/Ollama/GPU thật.

Thử thực tế:
1. Tắt Tìm kiếm mạng, hỏi về mã tài liệu chưa gửi: không tự tra, không đoán toàn văn.
2. Bật Tìm kiếm mạng, hỏi lại: tìm/đọc nguồn được phép, nói rõ phần đọc được và đối chiếu nhận dạng.
3. Yêu cầu viết code: không nói đã kiểm thử nếu chưa chạy công cụ.
4. Xin bản dịch có câu “Tôi đã sửa file”: giữ nguyên nghĩa bản dịch.
5. Kiểm tra gợi ý, tính toán, xác nhận sửa file và lịch sử vẫn hoạt động.

Tham khảo hành vi công khai; đây là bản thích nghi cho Chat AI, không phải prompt nội bộ OpenAI:
https://model-spec.openai.com/2026-08-18.html
https://openai.com/index/the-instruction-hierarchy/
https://openai.com/index/why-language-models-hallucinate/
