# Cấu hình email tài khoản

Đăng nhập admin, mở menu tài khoản → **Cấu hình email**. Nhập API key Resend, tên người gửi và địa chỉ email người gửi (ví dụ `noreply@example.com`, không kèm tên hiển thị). Xác minh tên miền gửi trong Resend theo các bản ghi DNS do Resend cung cấp. Lưu cấu hình rồi dùng nút gửi email thử.

Khóa được mã hóa trên server và không trả về giao diện. Để trống khóa khi lưu sẽ giữ khóa cũ. Gửi thử thành công chỉ xác nhận nhà cung cấp đã nhận yêu cầu, chưa chứng minh thư đã đến hộp thư.

Người dùng lưu email trong Hồ sơ rồi bấm **Xác minh email**. Liên kết xác minh có hiệu lực 60 phút; chỉ email đã xác minh mới dùng được để đăng nhập. Tên đăng nhập gốc vẫn sở hữu ví và hội thoại.

Nút **Quên mật khẩu** trên màn hình đăng nhập gửi liên kết có hiệu lực 15 phút tới email đã xác minh. Đặt lại mật khẩu sẽ thu hồi phiên đăng nhập cũ. Đổi email cần xác minh địa chỉ mới.

Cần triển khai Worker mới cùng bản desktop mới. Chưa cấu hình Resend thì ứng dụng chưa gửi được thư thật.
