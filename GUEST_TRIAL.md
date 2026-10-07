# Dùng thử 3 lượt trước khi đăng nhập

Giao diện giữ nguyên. Khách có thể gửi ba câu hỏi bằng Ollama local; câu hỏi thứ tư mở hộp đăng nhập. Ô nhập vẫn giữ nội dung để gửi sau khi đăng nhập.

- Bộ đếm lưu SQLite, không đặt lại khi khởi động, tạo hội thoại mới hoặc đăng xuất.
- Mỗi câu hỏi được chấp nhận tính một lượt. Đầu vào không hợp lệ không tính. Nếu đã chấp nhận rồi Ollama gặp lỗi, lượt vẫn được tính.
- Vòng gọi công cụ, xác nhận thao tác và tiếp tục lượt đang chạy không tăng bộ đếm; lượt thứ ba vẫn hoàn tất được.
- Khi đăng nhập, lịch sử khách được chuyển vào tài khoản vừa đăng nhập. Dữ liệu và ký ức tài khoản khác không được dùng cho khách.
- Nút Tìm kiếm mạng vẫn là điều kiện bắt buộc để truy cập web.

Các file: `assistant/trial.py` mới, `desktop_ui.py` sửa, `tests/test_trial.py` mới.

Giới hạn hiện tại theo cơ sở dữ liệu của bản cài, không phải giới hạn xác thực mỗi người trên server. Xóa dữ liệu local có thể đặt lại lượt. Chưa tích hợp Cloudflare AI trong thay đổi này. Nếu dùng Cloudflare trả phí, phải kiểm soát quota bằng server và giới hạn tổng ngân sách; không dùng bộ đếm local để bảo vệ chi phí.

Kiểm thử: `python -m unittest discover -s tests -q`. Đây là kiểm thử logic; cần chạy `run.bat` trên Windows để kiểm tra cửa sổ Qt và Ollama thật.
