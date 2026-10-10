# Kết nối điện thoại với ChatAI Windows

Android 0.4 + bản desktop/Worker cùng thay đổi này. GitHub Actions triển khai
`work.js` và tạo APK thử nghiệm riêng; chỉ dùng sau khi cả hai workflow đạt.
Windows cập nhật nguồn rồi mở lại; bộ cài cần build lại để có thư viện tạo QR.
Nếu chưa có qrcode, dùng mã JSON hiển thị dưới QR và Dán mã trên Android.

## Ghép và cấp quyền

Windows: Tài khoản → Kết nối điện thoại hoặc Cài đặt → Nâng cao → Kết nối điện thoại.
Android: Máy tính → Quét QR. QR có mã ngẫu nhiên 256-bit, dùng cho cùng tài khoản,
hết hạn 5 phút. Windows phải xác nhận tên điện thoại. Khóa desktop được DPAPI bảo vệ;
khóa điện thoại dùng Android Keystore. D1 chỉ giữ hash khóa kết nối.

Kết nối này cấp gửi tác vụ, xem tiến trình/kết quả văn bản và dừng/tiếp tục; không
có remote shell hoặc quyền truy cập máy tùy ý. Bộ thực thi ChatAI vẫn dùng các
quyền/thư mục/công cụ đã cấu hình. Thu hồi thiết bị sẽ chặn lệnh mới, hủy lệnh
chưa nhận và gửi yêu cầu hủy tác vụ đang chạy của thiết bị đó.

Checkbox Windows là **nhận việc mới**; tắt không ngắt tác vụ đang thực hiện.
Chương trình nhận phải đang mở trong phiên Windows đăng nhập, có kết nối Internet.
Không mở cổng Internet vào Windows. Android đồng hành không thay thế khóa thiết bị
Windows khi đăng nhập. Chưa chạy như Windows service hoặc tự khởi động cùng máy.

## Tác vụ và khôi phục

Mã tác vụ UUID được lưu trên Android trước khi gửi, giữ nguyên khi thử lại sau
mất mạng; server đối chiếu cả chủ sở hữu, desktop, mobile và nội dung. Mỗi desktop
chỉ nhận một tác vụ; thao tác nhận là UPDATE có điều kiện và RETURNING. Tác vụ đã
nhận không tự trở về queued khi mất kết nối. Kết quả có lease_id và phiên bản để
bỏ qua tiến trình cũ. Sau khi tiến trình desktop chết, tác vụ chưa rõ kết quả bị
báo lỗi, không tự chạy lại.

Dừng/tạm dừng qua stop flag của executor, chờ công cụ hiện tại trả quyền điều khiển.
Tiếp tục là lượt AI tiếp theo dùng hội thoại đã lưu, không chạy lại từ đầu tự động.
Nếu có bản nháp hoặc tác vụ cục bộ, không ghi đè để nhận việc từ điện thoại.
Khi PLAXIS Input đang mở và yêu cầu đề cập PLAXIS, không bắt đầu tác vụ mới.

Trạng thái completed là lượt executor kết thúc, không chứng nhận mô hình kỹ thuật
đúng. Đọc kết quả, các giới hạn và kiểm tra mô hình/báo cáo như trên desktop.

## Dữ liệu và tải server

Bảng remote_desktops, remote_pairs, remote_links, remote_tasks tạo thêm, không
thay thế bảng tài khoản/ví/hội thoại. Index riêng cho hàng đợi, tác vụ đang chạy,
yêu cầu ghép chờ và danh sách của điện thoại. Desktop tick 20 giây khi rảnh,
10 giây khi có việc; điện thoại chỉ poll khi màn hình Máy tính đang mở, lùi tới
60 giây khi lỗi. Không đọc lại toàn bộ thống kê ví hoặc lịch sử mỗi tick.

## Phạm vi và kiểm tra triển khai

Có lệnh chữ/giọng nói, hàng đợi, tiến trình, kết quả văn bản, bổ sung, dừng/tiếp tục,
thu hồi kết nối và yêu cầu ảnh màn hình. Chưa có gửi file lên Windows, tải file kết quả,
điều khiển chuột/phím trực tiếp hay push notification.

Kiểm thử trên Windows/Android thật trước dùng rộng rãi:
- Ghép đúng/sai tài khoản; QR hết hạn; từ chối và thu hồi quyền.
- Gửi yêu cầu đọc file vô hại trong whitelist, nhận đúng kết quả.
- Gửi cùng mã sau mất mạng chỉ thực hiện một lần; máy bận thì chờ.
- Tạm dừng/tiếp tục/hủy và tắt/mở app Android khi đang chờ.
- Đóng desktop giữa tác vụ phải báo chưa rõ kết quả, không tự chạy lại.
- PLAXIS đang có mô hình phải giữ nguyên.

Kiểm thử HTTP/SQLite giả lập không thay thế các kiểm tra này. Cloud environment
không có phiên Windows/PLAXIS và hiện không tải được Flutter SDK để build cục bộ.

## Ảnh màn hình theo yêu cầu

Windows: trong Kết nối điện thoại, bật “Cho phép điện thoại yêu cầu ảnh màn hình
trong phiên này”. Mặc định tắt và tắt lại khi tạo phiên mới. Android: Máy tính →
Yêu cầu ảnh màn hình. Chụp màn hình chính, có thể chứa ứng dụng khác; chỉ bật khi
đồng ý chia sẻ dữ liệu hiển thị. Mỗi yêu cầu chụp một lần, không tự chụp định kỳ.

Ảnh JPEG tối đa 1600×1000 và 600 KB, gửi HTTPS trên thread riêng; nội dung mã hóa
AES-GCM trong KV, TTL 5 phút. Server cần binding MEMORY_KV/CHAT_AI_KV/KV và secret
MEMORY_ENCRYPTION_KEY (32 byte base64) đã dùng cho bộ nhớ cá nhân. Thiếu cấu hình
thì báo lỗi, không lưu ảnh dạng rõ. Ảnh không được đính vào hội thoại hay tự gửi
cho nhà cung cấp AI. Android chỉ tải ảnh sau yêu cầu, không tải lại mỗi tick.
Thu hồi quyền chặn tải ảnh; hết hạn không xem lại qua API.

Yêu cầu bị mất phản hồi không tự chụp lại. Có thể gửi yêu cầu mới sau khi yêu cầu
cũ hết hạn. Cần thử trên Windows thật: tắt quyền phải bị từ chối, bật quyền nhận
đúng màn hình, thu hồi không xem được, ảnh hết hạn.
