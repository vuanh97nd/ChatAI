# Lưu và khôi phục hội thoại

Desktop 2.6.6 tự đồng bộ nội dung hội thoại theo tài khoản khi đăng nhập, sau khi hoàn tất lượt xử lý và mỗi 15 giây khi ứng dụng rảnh. SQLite trên máy là bộ nhớ đệm khi mất mạng; lần đồng bộ tiếp theo sẽ gửi phần chưa lưu. Mở lại ứng dụng sẽ khôi phục hội thoại gần nhất của tài khoản.

Các endpoint POST `/api/conversations/sync/list`, `/get`, `/put` dùng xác thực tài khoản hiện có. D1 tự tạo bảng `desktop_history` ở lần gọi đầu tiên. Khóa chính gồm tài khoản và mã hội thoại. PUT dùng revision để tránh ghi đè thay đổi trên thiết bị khác. Khi có hai bản sửa khác nhau, ứng dụng giữ thêm bản trên máy; khi xóa, server đánh dấu ẩn, giữ nội dung để hoàn tác.

Đồng bộ văn bản user/assistant, kết quả công cụ, tiêu đề, model và chế độ hội thoại. Không chuyển khóa API, hàng đợi thực thi, quyền đã cấp, ảnh hay tệp gốc. Những tệp này vẫn ở máy đã gửi. Hội thoại đang chạy không được thay thế bởi bản tải xuống. Một bản văn bản tối đa 1,5 MB; vượt giới hạn hoặc lỗi mạng vẫn giữ nguyên bản trên máy và báo trong tooltip trạng thái tài khoản.

Ngữ cảnh DeepSeek giữ tối đa 36 lượt gần đây với ngân sách 90.000 ký tự, kèm tối đa 8.000 ký tự thông tin người dùng ở các lượt trước. Lời nhắc yêu cầu dùng thông tin đã chốt, không hỏi lại và theo chủ đề mới khi người dùng đổi chủ đề. Lịch sử lưu đầy đủ không có nghĩa mọi cuộc hội thoại dài vô hạn đều nằm trong ngữ cảnh của model.

Lập kế hoạch JSON dùng tối thiểu 2.048, mặc định 4.096 token; nếu JSON bị cắt, thử lại một lần với tối đa 8.192 token trước khi thực thi. DeepSeek dùng chế độ JSON và tắt thinking trong lượt kế hoạch để không dùng hết ngân sách trước khi trả JSON. Các lượt trò chuyện thông thường giữ cấu hình model của người dùng.
