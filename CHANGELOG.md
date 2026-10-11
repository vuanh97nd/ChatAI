# Lịch sử cập nhật Chat AI

## Desktop 3.0.0

- Chọn bài tutorial theo manual và 2D/3D, giữ case trong ngữ cảnh; không gom bảng kiểm/tọa độ từ manual khác hoặc dùng trang cùng số của file khác để xác nhận đã đọc.

- Giảm lượt sửa lỗi phase bằng ánh xạ CalculationType sang DeformCalcType khi API đích hỗ trợ; sửa đường gọi hướng dẫn tutorial trong bộ điều khiển trực tuyến.
- Đo/hiển thị thời gian phản hồi AI và ghi thời gian nhóm lệnh PLAXIS để phân biệt chờ model với tính toán.

- Bổ sung hướng dẫn ngắn theo 28 chương Tutorial 2D/3D 2025.1 và công cụ đọc riêng từng chương; phân biệt móng tròn 2D với Building 3D.

- Mở rộng xác minh Active theo loại tải/kết cấu/chuyển vị và phase; bổ sung chẩn đoán kiểu dữ liệu đọc về.
- Yêu cầu đối chiếu đúng bài/case manual, hệ tọa độ, vật liệu và ModelType trước khi dựng PLAXIS.

- Thêm lập kế hoạch vùng đào 2D theo cao độ borehole hiện tại, kiểm tra biên và đọc lại tọa độ sau vẽ; chặn vẽ lặp khi kết quả chưa rõ.

- Bổ sung cache đọc tài liệu, tính toán, ứng dụng và bộ nhớ tiến độ/lỗi công cụ theo tài khoản; có nút xóa cache riêng.
- Sửa nhóm tọa độ polygon bị lồng thừa khi gửi sang PLAXIS.

- Sửa PLAXIS Remote Scripting không nạp được trên Python 3.12: đóng gói setuptools hỗ trợ distutils và báo nguyên nhân import thực.
- Mở ứng dụng bằng hội thoại mới; đồng bộ lịch sử không tự chọn lại hội thoại cũ.

- Đồng bộ phiên bản PC: giao diện, updater, runtime và bộ cài Windows.
- Bổ sung COM, cầu nối ứng dụng và quyền tự thực hiện công việc.
- Bật sẵn tự cài thư viện hỗ trợ, gồm PLAXIS Remote Scripting.
- Giữ nguyên phiên bản Android.

## 2.6.6

- Đồng bộ phiên bản giao diện, khởi động, updater, runtime, bộ cài và API server thành 2.6.6.
- Tách cấu hình AI trực tuyến khỏi Ollama; sửa lỗi lưu độ sáng tạo do gửi mã AI trống.

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
