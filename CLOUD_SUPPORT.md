# Cloudflare, Hỗ trợ và Cài đặt

Đã giữ giao diện và các nút hiện có; thêm Hỗ trợ ở thanh bên và trong menu Cài đặt, nút Lưu cài đặt.

## Sử dụng

- AI mặc định là Cloudflare AI; mô hình local mặc định vẫn qwen2.5:7b. Có thể đổi AI mặc định trong Cài đặt rồi bấm Lưu cài đặt.
- Cloudflare trả lời chat văn bản có streaming. Không hiện số lượt. Sau câu trả lời thứ ba, hiện “Vui lòng chuyển sang mô hình ngôn ngữ khác để tiếp tục trò chuyện.” và hộp Chọn mô hình. Câu hỏi thứ tư cũng bị server từ chối nếu vẫn chọn Cloudflare.
- Chọn model trên máy giữ hội thoại. Model chưa có sẽ hỏi trước khi tải. Ảnh, tài liệu đính kèm và Office/Python/tạo ảnh/video dùng công cụ local hiện có; bản tích hợp cloud này không tự gửi những tệp đó lên server.
- Chỉ gửi yêu cầu tra web khi nút Tìm kiếm mạng được bật. Cloud sử dụng dịch vụ tra mạng hiện có trên Worker (BRAVE_SEARCH_API_KEY); local giữ công cụ Bing đang có.
- Lượt được lưu D1, tính tổng cộng theo tài khoản. Khách có mã riêng của bản cài; khi dùng cloud sau đăng nhập, lượt khách được chuyển vào tài khoản một lần. Xóa dữ liệu khách trước đăng nhập có thể tạo danh tính mới; đây không phải cách bảo đảm một người chỉ có một danh tính. Không có miễn quota cho tài khoản quản trị viên.
- Lỗi trước khi có nội dung được hoàn lượt. Có nội dung trả lời một phần rồi bị ngắt vẫn tính lượt. Bộ đếm ngân sách chung không được hoàn vì yêu cầu upstream có thể đã phát sinh chi phí.
- Giới hạn request tổng ngày mặc định 100, cấu hình bằng CLOUD_DAILY_REQUEST_LIMIT. Đây là hàng rào bổ sung theo số yêu cầu, không phải đo chính xác Neurons; cần theo dõi Dashboard Cloudflare và ngân sách thực tế.

## Hỗ trợ

Năm mục: Gửi yêu cầu hỗ trợ, Báo lỗi, Góp ý tính năng, Hướng dẫn sử dụng, Yêu cầu của tôi. Có Quay lại chat.

Đăng nhập để gửi/xem yêu cầu. Báo lỗi có các loại Đăng nhập, Tải model, AI trả lời, Lỗi ứng dụng. Mỗi tin nhắn có thể đính kèm một ảnh hoặc tệp tối đa 1 MB. Chọn tệp và tên được hiển thị trước khi gửi. Không tự đính kèm log, mật khẩu hoặc lịch sử chat. Tệp nhận về chỉ được lưu khi người dùng chọn, không tự mở/chạy.

Quản trị viên đăng nhập tài khoản có quyền system/admin; mở Hỗ trợ → Yêu cầu của tôi để xem các yêu cầu, trả lời và đổi trạng thái. Tài khoản thường chỉ được xem yêu cầu của chính mình. Trạng thái: Đã gửi, Đang xử lý, Đã trả lời, Đã đóng. Nút Hỗ trợ có chấm khi nhận tin chưa đọc; cập nhật mỗi 30 giây khi đã đăng nhập. Có nút Làm mới yêu cầu.

## Tài khoản và hồ sơ

Trang Tài khoản/Hồ sơ không hiển thị tên hoặc URL server. Khi chưa đăng nhập, có Đăng ký/Đăng nhập và Ghi nhớ đăng nhập tích sẵn. Khi đã đăng nhập, hiện thông tin, Chỉnh sửa thông tin cá nhân, Đổi mật khẩu và Đăng xuất; ẩn các nút đăng ký/đăng nhập trong trang Tài khoản.

Chỉnh sửa được Họ và tên, Ảnh đại diện, Email và Số điện thoại (hai mục liên hệ không bắt buộc). Tên đăng nhập chỉ đọc. Nút Lưu thông tin lưu trên D1 theo tài khoản đã xác thực, cập nhật tên/ảnh ở thanh bên và nạp lại sau đăng nhập trên thiết bị khác. Email chưa được xác minh hoặc dùng khôi phục mật khẩu.

Ảnh đầu vào tối đa 8 MB/16 triệu điểm ảnh, được thu nhỏ còn 256px và chuyển JPEG trước khi gửi; ảnh lưu tối đa 128 KB. Không chấp nhận SVG/HTML làm ảnh đại diện. Có Bỏ ảnh. Không thay mật khẩu, vai trò hay lịch sử khi cập nhật thông tin.

Các endpoint mới `/api/account/profile/get` và `/api/account/profile/update` yêu cầu Deploy work.js mới. Bảng account_profiles tự tạo, không cần nhập SQL thủ công. Chưa Deploy thì đăng nhập vẫn dùng cách cũ, nhưng chỉnh sửa hồ sơ chưa hoạt động.

Nhãn điều hướng và menu tải đổi thành Tải mô hình. Lưu cài đặt chỉ bật khi có thay đổi cấu hình; thông tin cá nhân được lưu riêng bằng Lưu thông tin.

## Cài đặt

Giao diện có lựa chọn Sáng/Tối và cỡ chữ chat. Xem trước ngay, chỉ ghi nhớ khi bấm Lưu cài đặt; Bỏ thay đổi khôi phục màu và cỡ chữ đã lưu. Các nút mở config.json và thư mục log/backup nằm trong Nâng cao. Đã bỏ nút Bộ nhớ cá nhân trên server trong phần Tài khoản.

Lưu cài đặt lưu cấu hình nguyên tử, tạo backup, áp dụng vào lượt chat tiếp theo và giữ nguyên trang. Nếu rời trang khi chưa lưu: Lưu, Bỏ thay đổi hoặc Ở lại. Đóng ứng dụng cũng kiểm tra thay đổi chưa lưu. Đổi URL server xóa phiên đăng nhập đã nhớ để không dùng nhầm tài khoản của server khác. Không cần khởi động lại cho các mục hiện có.

## Cập nhật Worker để chạy tính năng server

1. Mở Cloudflare Dashboard → Workers & Pages → Worker `chatai` → Edit code.
2. Thay code bằng toàn bộ `work.js` mới trong thư mục Chat-AI, bấm Deploy. `server/worker.js` có cùng nội dung cho người dùng Wrangler.
3. Giữ D1 binding tên `DB`, Workers AI binding tên `AI` và secret `ADMIN_KEY` hiện có. Không dán secret vào mã. Bộ nhớ riêng giữ các binding/secret hiện tại.
4. Các bảng quota và Hỗ trợ tự tạo trong D1; không xóa dữ liệu cũ và không cần chạy SQL thủ công.
5. Đóng/mở lại ứng dụng bằng `run.bat`. Chọn Cloudflare để chat; đăng nhập để dùng Hỗ trợ. Nếu chưa Deploy code mới, các endpoint mới chưa hoạt động.

Việc sửa file không tự triển khai Worker đang chạy. Chưa triển khai server thật hoặc chạy giao diện Windows/Qt/Ollama thật trong phiên chỉnh sửa này.

## Các file

Sửa: desktop_ui.py, assistant/config.py, assistant/accounts.py, assistant/trial.py, work.js, server/worker.js, server/tests/worker.test.js.

Mới: assistant/profile_ui.py, assistant/themes.py, assistant/cloud.py, assistant/support_ui.py, tests/test_cloud.py, tests/test_settings_apply.py, server/tests/product.test.js, CLOUD_SUPPORT.md.

Kiểm thử: `python -m unittest discover -s tests -q`; `node --test server/tests/*.test.js` (Node hỗ trợ node:sqlite). Kiểm tra quota đồng thời, chuyển lượt khách vào tài khoản, hoàn lượt lỗi, quyền truy cập yêu cầu và tệp, chưa đọc, SSE, cấu hình hợp lệ/không hợp lệ/backup. Kiểm thử server dùng SQLite thật và AI giả lập, không gửi yêu cầu hỗ trợ tới quản trị viên thật.
