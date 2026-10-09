# Thanh toán Chat AI

Trong menu tài khoản, chọn **Số dư và thanh toán**. Cửa sổ dùng cùng giao diện Qt và màu của ứng dụng.

- Cloud AI, NVIDIA và AI local miễn phí, không yêu cầu ví hoặc gia hạn để chạy.
- DeepSeek: 4.000 đ/1.000.000 token tổng đầu vào + đầu ra; không áp giới hạn token tháng. Các lượt đọc ảnh, suy luận và thử lại có usage đều tính phí.
- 30 ngày đầu kể từ ngày đăng ký miễn phí duy trì, vẫn cần nạp tiền token. Hết dùng thử: 100.000 đ/30 ngày, thanh toán riêng, không tự trừ ví để gia hạn.
- Ví token không hết hạn. Mệnh giá QR: 20.000 / 50.000 / 100.000 / 200.000 / 500.000 đ.
- OpenAI / ChatGPT đã có trong danh sách và cấu hình API; chưa có bảng giá, chỉ admin được kiểm tra/sử dụng, người dùng được báo chưa thiết lập. Tập trung tính phí DeepSeek trước.
- Admin hệ thống miễn phí; usage DeepSeek/NVIDIA vẫn có lịch sử khi thanh toán bật. Phí nhà cung cấp vẫn do chủ API thanh toán.

## Kết nối QR tự động (SePay)

1. Đăng nhập admin, mở tab **Quản trị thanh toán**. Nhập mã ngân hàng VietQR, số tài khoản, tên người nhận.
2. Kết nối ngân hàng với SePay. Tạo webhook **tiền vào**, URL hiển thị trong ứng dụng (`https://<worker>/api/billing/webhook`), xác thực **API Key**. Đặt cùng khóa webhook trong SePay và ứng dụng (tối thiểu 16 ký tự). Header gửi về phải là `Authorization: Apikey <khóa>`.
3. Lưu cấu hình rồi bật **Bật QR tự động và thu phí DeepSeek**. Chạy thử một giao dịch thực với số tiền và nội dung chính xác trước khi cho khách dùng. Mã cần thiết, dạng `CA` + 20 ký tự hex, nằm trong `content` của giao dịch.
4. Đối chiếu ví và lịch sử với giao dịch ngân hàng/SePay. Các test giả lập xác thực và sổ cái không thay thế kiểm thử ngân hàng thật.

QR VietQR chỉ tạo mã chuyển khoản, không xác nhận thanh toán. Chỉ webhook đã xác thực, đúng tài khoản nhận, chiều tiền vào, mã đơn, số tiền và còn hiệu lực mới được cộng. Webhook gửi lại không cộng lần hai. QR có hiệu lực 30 phút. Chuyển sai nội dung/số tiền hoặc quá hạn cần admin kiểm tra chứng từ và nạp thủ công; không cộng tự động.

Khóa webhook được mã hóa AES-GCM trong D1, không trả về client, không lưu trong cài đặt local. Mã hóa dùng secret ADMIN_KEY của Worker; đổi ADMIN_KEY cần lưu lại cấu hình thanh toán. Không đưa khóa vào hội thoại. Giữ cấu hình tắt nếu chưa kết nối ngân hàng.

## Admin và đối soát

- Nhập tên người dùng rồi **Xem ví người dùng** để xem lịch sử nạp, usage và các lượt đang giữ chỗ.
- **Nạp thủ công** yêu cầu số tiền và lý do/chứng từ; lưu người thực hiện. Gửi lại cùng mã yêu cầu không cộng lại. Nếu muốn một lần nạp khác cùng số tiền, ghi lý do/chứng từ mới.
- **Quản lý / khóa / mở khóa người dùng** mở trang quản lý tài khoản hiện có. Tài khoản bị khóa hoặc xóa không được dùng API; hết hạn duy trì vẫn được đăng nhập để thanh toán và dùng AI miễn phí.
- Lượt DeepSeek giữ chỗ theo ngân sách đầu vào/đầu ra, rồi trừ đúng `usage.total_tokens`, kể cả phản hồi rỗng đã tiêu token. Giá lưu bằng số nguyên milli-đồng để không sai do làm tròn.
- Khi dịch vụ không trả usage hoặc kết nối không rõ kết quả, số tiền giữ chỗ ở trạng thái **chờ đối soát**, không tự thu ước lượng. Admin kiểm tra usage nhà cung cấp, nhập mã lượt và token đã xác minh kèm lý do. Nhập 0 chỉ khi xác minh lượt không tiêu token.
- Với DeepSeek tính phí, Worker đọc JSON đầy đủ rồi trả nội dung cho desktop; không phụ thuộc client nhận khung usage cuối. Luồng trả dần trên API cũ chưa hỗ trợ tính phí được từ chối riêng cho DeepSeek, không chặn Cloud/NVIDIA/local.

## Triển khai

GitHub Actions triển khai `work.js` và giữ bindings/secrets hiện có. D1 tự tạo các bảng billing, không cần KV mới. Khởi chạy lại bản mã nguồn desktop sau khi cập nhật; bản EXE cần được build lại để có cửa sổ mới.

Cấu hình mặc định tắt; triển khai mã không tự kết nối SePay hay ngân hàng. Tất cả thu phí do Worker quyết định, client không được tự khai số token hay tự xác nhận tiền vào.
