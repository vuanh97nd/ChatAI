# Lịch sử cập nhật Chat AI

## 2.6.5

- Đồng bộ phiên bản ứng dụng, updater, Python runtime và bộ cài Windows.
- Đặt Cloudflare AI làm mặc định cho cấu hình mới và tài khoản mới.
- Thêm Qwen3 8B, cửa sổ Giới thiệu có logo/thông tin tác giả và biểu tượng cho các mục menu hỗ trợ, giới thiệu, quản lý người dùng.
- Cấu hình Inno Setup xuất bộ cài một file EXE có kèm Python runtime.

## 2.5.0

- Windows desktop với logo robot và màn hình khởi động có chấm chạy.
- Nạp backend/SQLite ở luồng nền, lazy-load công cụ Excel.
- Cài đặt model chat/code, token, ngữ cảnh, độ sáng tạo, số vòng tool, cỡ chữ, whitelist và dữ liệu.
- Model nhẹ và DeepSeek R1 8B trong danh mục tải.
- Ba chấm khi AI đang phản hồi; bấm để cuộn đến phần trả lời mới nhất.
- Tải module/model giảm ghi SQLite, có MB/s/ETA cho model; mô-đun tạo ảnh cho chọn SD-Turbo nhanh hoặc SDXL-Turbo chất lượng cao.
- Tạo tài khoản server tùy chọn với Họ và tên, Tên đăng nhập, Mật khẩu.
- Worker server đa provider, streaming, lịch sử riêng theo tài khoản, web sources và quản trị.
- Inno Setup source và Build-Setup.bat.
- Đăng nhập bắt buộc, ghi nhớ mặc định tích, mật khẩu che và DPAPI.
- Bộ nhớ riêng trên server KV mã hóa, D1 index theo tài khoản, tự nạp vào suy luận.
- Clipboard Ctrl+V/Ctrl+C ảnh, Gemma3 4B vision.
- Nút Tìm kiếm mạng thay hộp chọn chế độ trên đầu; Python search bridge tự động.
- Kiểm tra GitHub Releases, xem ghi chú và tải cập nhật có xác nhận.

## Mẫu cho bản tiếp theo

Khi phát hành phiên bản mới, tạo mục ghi cụ thể: tính năng thêm, lỗi sửa, thay đổi dữ liệu/phụ thuộc và hướng dẫn nâng cấp nếu có. Không liệt kê ý tưởng chưa triển khai như tính năng đã hoàn thành.
