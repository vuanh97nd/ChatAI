# Thẻ kinh nghiệm và theo dõi công việc Chat AI

Giữ nguyên giao diện/model. Không tải thư viện, không gọi thêm model để chọn thẻ, không thay đổi quyền web theo nút. Đây là hướng dẫn và điều phối bằng code, không huấn luyện trọng số hoặc biến phản hồi 👎 thành tri thức tự động.

File mới đầy đủ:
- assistant/experience.py: 32 thẻ, chọn tối đa 2 thẻ/1100 ký tự theo nhãn và từ khóa. Mỗi thẻ có dấu hiệu, dữ kiện cần, bước xử lý, lỗi tránh, ví dụ và điều kiện dừng.
- tests/test_experience.py: kiểm thử thẻ, lưu trạng thái, kết quả thật, chặn lặp lỗi và quyền trao đổi.
- EXPERIENCE.md: hướng dẫn này.
File sửa đầy đủ: assistant/agent.py.

Khi có thẻ phù hợp, thay phần ví dụ chung bằng thẻ; không dồn cả hai bộ vào cùng prompt. Trò chuyện ngắn không chọn thẻ. Không tăng số lượt gọi model cho chat thường.

Nhóm thẻ: khởi động Windows, môi trường Python/pip/venv, Ollama, tốc độ/GPU/tải model, traceback/test/sửa code/SQL, Excel/công thức/Office/PDF scan, nhận dạng tiêu chuẩn/tài liệu chưa đủ/nguồn mâu thuẫn/tin tức/thời tiết/lỗi web, tính phần trăm/đơn vị/ngày giờ/thống kê, dịch/email/kế hoạch/tình huống cần chính xác cao/ký ức/giải thích.

Theo dõi task_progress trong state SQLite của từng cuộc hội thoại. Chỉ ghi kết quả công cụ thực với dấu vân tay tham số; không nhận lời AI nói “đã làm” là bằng chứng. Đưa tối đa 4 bước gần đây vào ngữ cảnh để tránh hỏi lại và lặp cách xử lý. Lỗi được giới hạn độ dài, che một số mẫu khóa truy cập; không lưu thêm nguyên tham số vào sổ bước. Lịch sử/audit trước đây vẫn hoạt động như cũ.

Đếm lỗi giống hệt trong lượt hiện tại: cùng tên tool + cùng tham số thất bại 2 lần thì không thực thi lần 3. Đổi tham số/cách xử lý hoặc người dùng gửi một lượt mới sẽ có thể thử lại trong giới hạn có sẵn. Tool bị từ chối không được đề nghị lại nguyên thao tác trong cùng lượt. Các tool Python vẫn giữ giới hạn cũ; số lần đọc web cũng không vượt quyền nút tìm mạng.

Nhận biết pha trao đổi theo những từ như “chỉ đề xuất”, “trao đổi trước”, “chưa sửa”, “đừng sửa”. Khi đang trao đổi, chặn tool ghi trước khi tạo preview. Nếu người dùng yêu cầu “hãy sửa/rồi thực hiện”, không tự coi đó là chỉ trao đổi, nhưng vẫn giữ xác nhận/whitelist. Đây là quy tắc từ khóa, chưa hiểu mọi cách nói hay phủ định phức tạp. Khi câu mơ hồ, AI cần làm rõ; không nhận hệ thống có bộ theo dõi công việc hiểu hoàn hảo.

Thẻ là hướng dẫn chẩn đoán, không chứa kết luận đã xác minh hay dữ liệu hiện tại. Tra web chỉ khi nút Tìm kiếm mạng bật; không tự cài/xóa cache/chạy lệnh theo thẻ. Phản hồi 👎 vẫn là dữ liệu đánh giá, không tự thêm thẻ chưa được kiểm chứng.

Đợi Drive đồng bộ, đóng ứng dụng rồi chạy run.bat. Không cần cập nhật work.js.

Kiểm thử từ thư mục dự án:
```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
60 kiểm thử và compileall qua trong môi trường phát triển, gồm các kiểm thử cũ. Chưa chạy GUI Windows, model Ollama hoặc GPU thật.

Thử thực tế:
- “Ứng dụng tự tắt khi mở”: hướng dẫn lấy log đúng, không khuyên cài lại ngay.
- “Chỉ đề xuất trước, chưa sửa file”: không thực hiện tool ghi.
- “Hãy sửa theo ý tưởng vừa rồi”: thực hiện trong quyền UI hiện có.
- Lỗi tool lặp: không chạy cùng lời gọi thất bại vô hạn.
- Tắt Tìm kiếm mạng, hỏi tiêu chuẩn: không tự tìm, chỉ đề nghị bật nút/gửi tài liệu.
