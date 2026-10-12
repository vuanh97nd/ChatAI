# Đồng bộ bộ nhớ giữa hai tài khoản Cloudflare

Mã đã có trong cả `work.js` (dán vào Cloudflare Dashboard) và `server/worker.js`
(triển khai bằng Wrangler). Phải cập nhật **cả hai Worker**; cập nhật ứng dụng
Windows/Android không tự triển khai Worker. Mặc định tính năng tắt.

## Phạm vi

- Bộ nhớ cá nhân `/api/memory/personal`: sao chép nội dung sau khi giải mã ở server
  nguồn, truyền HTTPS, mã hóa lại bằng khóa MEMORY_ENCRYPTION_KEY của server đích.
- Bài học cách làm `/api/lessons`: riêng theo tài khoản đã ghép; bài học chung chỉ
  đồng bộ nếu quản trị viên bật MEMORY_SYNC_SHARED ở cả hai server.
- ID được giữ nguyên; thay đổi mới hơn được áp dụng theo timestamp UTC từng mục.
  Cùng timestamp nhưng khác nội dung: giữ nguyên, báo conflict, không tiến cursor.
- Xóa ghi nhớ cá nhân/thu hồi bài học chung được truyền bằng tombstone để bản cũ
  không xuất hiện lại. Bài học riêng hiện chưa có API xóa riêng.
- Không sao chép mật khẩu, ví, lịch sử chat, tệp PDF gốc, cache, hàng đợi hay trạng
  thái thao tác CAD/PLAXIS. Không tự tạo/đồng bộ tài khoản: tài khoản ghép phải có
  sẵn ở cả hai server và đang active. Khác tên vẫn ghép được khi admin xác nhận.

## Cấu hình trong Cloudflare

Vào từng Worker → Settings → Variables and Secrets. Các trường bên dưới là biến
mới cần thêm; giữ các binding DB/KV và các khóa AI hiện tại.

1. Triển khai mã mới và bảo đảm bộ nhớ cá nhân đã dùng được trên từng server:
   binding MEMORY_KV (hoặc CHAT_AI_KV/KV), secret MEMORY_ENCRYPTION_KEY của riêng
   server đó. Không cần đặt hai khóa mã hóa bộ nhớ giống nhau.
2. Tạo khóa đồng bộ ngẫu nhiên một lần, đặt dưới **Secret** tên
   `MEMORY_SYNC_KEY` giống nhau trên hai Worker, tối thiểu 32 ký tự. Đây không
   phải mật khẩu người dùng/admin và không nhập vào app. Có thể tạo trên máy:

   ```powershell
   $bytes = New-Object byte[] 32
   $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
   $rng.GetBytes($bytes)
   $rng.Dispose()
   Set-Clipboard ([Convert]::ToBase64String($bytes))
   ```

   Dán khóa clipboard vào trường Secret của hai Worker; không gửi khóa vào chat.
3. Trên **server cũ** `chatai.anhvn53.workers.dev`, thêm biến Text:

   | Tên | Giá trị ví dụ |
   |---|---|
   | MEMORY_SYNC_PEER | `https://chatai-backup.vuanh97nd1.workers.dev` |
   | MEMORY_SYNC_ACCOUNTS | `[{"local":"alice","remote":"alice_backup"}]` |
   | MEMORY_SYNC_SHARED | `true` nếu muốn đồng bộ bài học chung |

4. Trên **server mới/dự phòng**, đảo chiều cặp tài khoản:

   | Tên | Giá trị ví dụ |
   |---|---|
   | MEMORY_SYNC_PEER | `https://chatai.anhvn53.workers.dev` |
   | MEMORY_SYNC_ACCOUNTS | `[{"local":"alice_backup","remote":"alice"}]` |
   | MEMORY_SYNC_SHARED | giống lựa chọn server cũ |

   Thay alice/alice_backup bằng tài khoản thực của cùng người. Không tự ghép chỉ
   vì trùng tên. Mỗi tài khoản ghép tối đa một đối tác. Nếu cần bộ nhớ riêng admin,
   thêm cặp `{"local":"admin","remote":"admin"}` ở cả hai phía; không cho ghép
   admin với tài khoản thường. Bài học chung đã xuất bản không cần ghép admin. Chỉ đồng bộ chung
   thì để MEMORY_SYNC_ACCOUNTS=`[]`. Tối đa 100 cặp cấu hình.
5. Bật Cron Trigger `*/15 * * * *` ở **cả hai Worker** và Deploy cấu hình.

## Kiểm tra kết quả

Tạo một ghi nhớ thử có nội dung vô hại ở server A. Sau lượt cron, đăng nhập tài
khoản đã ghép ở server B và mở Bộ nhớ cá nhân. Sửa nội dung tại B, đợi lượt cron
của A; xác nhận nội dung mới tại A. Xóa ghi nhớ thử, xác nhận phía kia cũng xóa.

Workers Logs ghi `memory_sync` với các bộ đếm `written`, `conflicts`, `errors`.
Không ghi nội dung ghi nhớ hoặc khóa. `errors=0` và `conflicts=0` cho biết lượt
đồng bộ không gặp lỗi; `written=0` có thể là hai bên đã giống nhau. Nhiều dữ liệu
có thể cần nhiều lượt; mỗi lượt tối đa 40 yêu cầu tới peer, 20 mục/trang,
10 trang/loại/tài khoản; các cặp tài khoản được luân phiên để tránh bỏ đói cặp sau.

Admin có thể chạy ngay qua `POST /api/admin/memory-sync/run`, dùng cơ chế xác thực
admin hiện có (JSON username/key); phản hồi chứa result với các bộ đếm trên.
Route `/api/internal/memory-sync/export` chỉ nhận khóa đồng bộ qua Bearer header;
đăng nhập người dùng thường hoặc biết tên tài khoản không đủ để xuất bộ nhớ.

Nếu một server mất kết nối, cursor không tiến qua dữ liệu chưa áp dụng; lượt sau
thử lại. Các app vẫn dùng bộ nhớ server còn hoạt động hoặc bộ nhớ local hiện có.
Tài khoản bị khóa hoặc thiếu ở một phía thì dữ liệu riêng không được chuyển.
Conflict cùng phiên bản phải được admin/người dùng sửa nội dung để tạo phiên bản
mới rồi đồng bộ lại. Đây là đồng bộ cuối cùng nhất quán, không phải giao dịch
đồng thời trên cả hai D1; đồng hồ server phải là UTC và không chỉnh ngược.

Để tắt, bỏ MEMORY_SYNC_PEER/MEMORY_SYNC_KEY ở cả hai Worker. Không xóa dữ liệu
đã đồng bộ. Thay khóa thì cập nhật cả hai phía; khóa lệch sẽ bị từ chối.
