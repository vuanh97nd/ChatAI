# 30 câu kiểm thử chất lượng

questions.json gồm 30 câu, nhóm và tiêu chí kiểm chứng. Đây là bộ đánh giá thủ công, không phải bằng chứng model đã trả đúng 30 câu. Kiểm thử tự động trong tests kiểm tra hoạt động phần mềm bằng backend giả lập.

Chạy mỗi câu trong cuộc chat mới, cùng qwen2.5:7b, cùng num_ctx, công cụ và tập tài liệu. Giữ các câu 28–29 trong cùng tài khoản để kiểm tra ghi nhớ. Câu 25–27 cần đính kèm/index một tài liệu mẫu không nhạy cảm. Câu 30 dùng hai tài khoản thử nghiệm. Tin mới cần ghi thời gian và lưu kết quả web để so sánh công bằng. Trước/sau phải dùng cùng dữ kiện; không so những lần tin tức đã thay đổi mà coi chênh lệch là lỗi prompt.

Chấm mỗi chiều 0–4: accuracy (đúng kiến thức/số liệu), relevance (đúng nhu cầu), usefulness (làm được việc/bước cụ thể), grounding (nguồn và trung thực về giới hạn), clarity (rõ, đủ, gọn). 0: sai nghiêm trọng/thiếu; 1: nhiều lỗi; 2: dùng được nhưng còn thiếu; 3: tốt; 4: đáp ứng đầy đủ tiêu chí. Tổng tối đa 20/câu. Ghi riêng thời gian phản hồi và số lần gọi model/tool; không chỉ tối ưu điểm mà bỏ tốc độ.

Mỗi dòng trong before.jsonl hoặc after.jsonl:
```
{"id":1,"accuracy":4,"relevance":4,"usefulness":3,"grounding":4,"clarity":4}
```
Từ thư mục Chat-AI:
```
.venv\Scripts\python.exe evaluation\score.py before.jsonl after.jsonl
```
Chỉ tính chênh lệch khi hai tập có cùng ID. Không tạo điểm giả cho câu chưa kiểm thử.

Đánh giá 👎 trong ứng dụng lưu câu hỏi, bản trả lời, model, nhãn phân loại, lý do và thời gian trong bảng answer_feedback thuộc SQLite local. Có thể đọc bằng FeedbackStore.poor_answers(username) trong mã đã xác thực tài khoản. Gom các lỗi cùng loại, sửa prompt/quy trình, chạy lại bộ 30 câu cùng câu gây lỗi. Thay từng yếu tố một và giữ bản trước để phát hiện hồi quy. Phản hồi không tự huấn luyện model và không tự gửi nội dung lên dịch vụ ngoài.

Giữ 7B cho máy hiện tại. Chỉ cân nhắc 14B khi 7B vẫn sai ở các câu suy luận khó dù đã có dữ liệu/công cụ đúng, và bạn chấp nhận chậm hơn hoặc có thêm VRAM. Với cấu hình RTX 3070 8GB, bản 14B quantized có thể phải offload RAM; đo thực tế trước khi đổi. Chưa đổi model mặc định trong bản cập nhật này. Nếu dùng hai model sau này: model nhỏ phân loại, model lớn trả lời câu khó; tránh đổi model ở mỗi lượt trò chuyện ngắn vì thời gian nạp có thể xóa lợi ích tốc độ.
