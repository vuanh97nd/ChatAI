# Thanh toán tập trung tại server dự phòng

## Phân vai

- Chính: `https://chatai.anhvn53.workers.dev` — đăng nhập, tài khoản, AI,
  cấu hình key AI, tài liệu, hội thoại, bộ nhớ và các chức năng khác.
- Dự phòng: `https://chatai-backup.vuanh97nd1.workers.dev` — sổ ví,
  cấu hình ngân hàng/giá, đơn QR, webhook, lịch sử thu/chi và quyết định đối soát.
- PC/Android vẫn gọi API chính bằng phiên đăng nhập của chính nó. Worker chính
  xác thực người dùng, ký yêu cầu thanh toán HMAC-SHA256 rồi gửi sang dự phòng.
  Không chuyển mật khẩu, session token, key AI hay ADMIN_KEY sang server kia.
  Khóa webhook ngân hàng chỉ được chuyển khi cấu hình hoặc chuyển sổ đã được
  quản trị viên yêu cầu; HTTPS và liên kết ký xác thực bảo vệ yêu cầu đó.

Mặc định `BILLING_ROLE=local` (hoặc không đặt biến) giữ nguyên hành vi cũ.
Cập nhật mã PC hoặc git pull không tự triển khai Worker/chuyển ví thật.

## Khi dự phòng mất kết nối

Không tạo đơn, QR, nạp thủ công, gia hạn, thay giá hoặc thay số dư. Không ghi
giao dịch nạp vào một ví cục bộ thay thế. Webhook nhận 503 để phía ngân hàng
có thể thử lại; không xác nhận nhận tiền khi chưa ghi vào sổ dự phòng.
Ẩn QR trên PC/Android khi phát hiện lỗi thanh toán. QR đã phát hành trước khi
mất kết nối vẫn có thể được người dùng thanh toán bên ngoài ứng dụng; cần
đối soát webhook sau khi dịch vụ phục hồi, không thể thu hồi giao dịch ngân hàng.

AI tiếp tục chạy trên chính bằng **tiền đã được dự phòng cấp hạn mức trước đó**.
Dự phòng giữ chỗ toàn bộ hạn mức, nên nó không thể được cấp cho nơi khác nữa.
Chính giữ chỗ tiền từng lượt trước khi gọi AI và chỉ trừ theo usage xác thực.
Chưa có hạn mức đã xác nhận, hết tiền khả dụng, hoặc phí duy trì đã hết hạn thì
không gọi AI có tính phí. Không lấy số dư hiển thị/cache làm nguồn cấp tiền.
Hạn mức đầu ra được giữ trước nên lượt AI có thể bị từ chối khi số dư quá thấp,
kể cả khi một câu trả lời ngắn thực tế có thể rẻ hơn.

Khi nối lại, tổng tiền đã chi được đối soát theo số tích lũy tăng dần. ID cấp
hạn mức được lưu trước khi gửi, nên mất phản hồi không tạo tiền lần nữa.
Đồng bộ khi gọi AI, xem ví và cron 15 phút. Lịch sử từng lượt chuyển theo lô
100 dòng/lần; số tổng tiền có thể được cập nhật trước phần lịch sử chi tiết.
Lượt chưa có usage giữ tiền và chờ admin quyết định; quyết định từ dự phòng
được chính áp dụng rồi xác nhận, không trừ thêm ngay ở cả hai nơi.

## Chuẩn bị trước khi bật

1. Sao lưu D1 của **cả hai server** và cấu hình thanh toán trước khi chuyển.
2. Chuẩn bị danh sách đầy đủ tài khoản chính → chủ ví tại dự phòng. Đây là
   ánh xạ chủ ví, không phải đồng bộ tài khoản/mật khẩu. Không tự ghép chỉ vì
   trùng tên. `admin` ánh xạ riêng sang `admin` và phải được chính xác thực admin.
3. Không đổi hostname/source, xóa bảng `billing_spend_*`, đổi ánh xạ chủ ví hoặc
   xoay sang ví khác khi còn tiền đã cấp/chưa đối soát. Đó là dữ liệu tài chính,
   phải đối soát trước khi thực hiện phục hồi/chuyển server tiếp theo.
4. Triển khai cùng bản `work.js` hoặc `server/worker.js` lên **cả hai Worker**,
   giữ nguyên các binding DB/KV/AI/secrets đang có. Chưa đặt role mới thì mã cũ
   vẫn hoạt động. Hai tài khoản Cloudflare có thể cần hai token triển khai khác nhau.

## Biến và secret mới trên Cloudflare

Tạo một secret ngẫu nhiên tối thiểu 32 ký tự tên `BILLING_LINK_KEY`, giống nhau
trên hai Worker. Không dùng ADMIN_KEY, key nhà cung cấp hoặc khóa webhook cho
mục này. Không đưa secret vào repo, console log hoặc hội thoại.

| Biến | Chính | Dự phòng |
|---|---|---|
| `BILLING_ROLE` | `primary` | `authority` |
| `BILLING_AUTHORITY_URL` | `https://chatai-backup.vuanh97nd1.workers.dev` | không cần |
| `BILLING_PUBLIC_ORIGIN` | `https://chatai.anhvn53.workers.dev` | không cần |
| `BILLING_PRIMARY_URL` | không cần | `https://chatai.anhvn53.workers.dev` |
| `BILLING_ACCOUNT_MAP` | JSON như `{"alice":"alice","bob":"bob"}` đã đối chiếu | không cần |
| `BILLING_MIGRATION_FREEZE` | `true` trong khi chuyển, sau đó `false` | tương tự |

Không điền dấu `/` hoặc đường dẫn sau hostname; URL phải HTTPS.
Liên kết chỉ tin cậy đúng một server chính. Chưa ghép người dùng sẽ không tự
tạo ví mới/cấp hạn mức cho một danh tính tùy ý.

## Chuyển sổ đang có (không tự cộng hai ví)

Sau khi đã sao lưu, đặt `BILLING_MIGRATION_FREEZE=true` và cấu hình role/link
ở cả hai Worker. Tạm dừng gọi AI/giao dịch, đợi các lượt đang chạy kết thúc.
Giữ freeze đến khi chuyển sổ đã được kiểm tra xong.

Kiểm tra liên kết trước (không chuyển tiền hay đơn):

```powershell
& '.\runtime\python\python.exe' '.\scripts\migrate_billing_to_backup.py' --check
```

`Connected: True` xác nhận liên kết ký được dự phòng chấp nhận. Kết quả không
in khóa. Nếu lỗi: `BILLING_PUBLIC_ORIGIN_INVALID` là địa chỉ nguồn thiếu/sai;
`BILLING_LINK_AUTH_OR_ORIGIN_MISMATCH` là khóa hoặc nguồn không khớp;
`BACKUP_AUTHORITY_ROLE_OR_CODE_MISSING` là dự phòng thiếu role/mã;
`BILLING_LINK_NON_JSON_HTTP_403` là HTTP 403 không trả JSON (kiểm tra Security
Events); `BILLING_LINK_NETWORK/TIMEOUT` là lỗi kết nối/chờ. Đừng bỏ freeze
hoặc đổi ID chuyển sổ để xử lý lỗi liên kết.

Chạy trên máy Windows có phiên admin **server chính** đã lưu trong Chat AI:

```powershell
& '.\runtime\python\python.exe' '.\scripts\migrate_billing_to_backup.py' --request-id '<UUID cố định cho lần chuyển này>' --confirm
```

Lệnh chỉ nhận phiên admin đã lưu, không in token hoặc yêu cầu đưa khóa vào chat.
Nếu timeout, chạy lại **cùng UUID**. Không dùng UUID mới để thử cộng tiền lại.
Số dư, tiền giữ chỗ, hạn duy trì, đơn, biên nhận, usage và đơn giá lịch sử được
chuyển nguyên giá trị milli-VND. Ngân hàng/khóa webhook được mã hóa lại bằng
khóa của dự phòng. Dữ liệu chính cũ giữ nguyên như bản lưu, không tiếp tục chi.

Đích phải chưa có dữ liệu ví/đơn/usage hoặc cấu hình ngân hàng riêng. Nếu đã có,
API từ chối thay vì ghi đè/cộng gộp tự động; cần đối chiếu hai sổ và chuẩn bị
migration riêng. Snapshot tối đa 10.000 dòng mỗi bảng; lớn hơn cần chuyển D1
theo kế hoạch riêng. Không xóa dữ liệu thật để vượt điều kiện này.

Đối chiếu số tài khoản, số dư, held, hạn duy trì, lịch sử và bảng giá. Sau đó
bỏ freeze trên dự phòng, rồi chính. Mở ví ở chính và thử một lượt AI có usage.
Cấu hình webhook SePay nên trỏ thẳng về:
`https://chatai-backup.vuanh97nd1.workers.dev/api/billing/webhook`.
Đường webhook cũ ở chính vẫn chuyển tiếp có xác thực để xử lý đơn QR cũ.

PC cần bản `assistant/billing_ui.py` mới để ẩn QR/khóa nút khi offline.
Android cần build APK mới; server vẫn từ chối giao dịch nạp từ APK cũ khi offline.
Android mới mặc định server chính; phiên đã lưu ở endpoint khác không được
tự chuyển credential qua endpoint mới, người dùng đăng nhập lại server chính.

## Kiểm tra

```bash
python scripts/build_billing_central.py
node --test server/tests/billing-central.test.js server/tests/billing.test.js
```

Kiểm tra thực sau cấu hình: wallet/QR ở dự phòng; key AI và request AI ở chính;
tạm ngắt liên kết dự phòng → nạp/QR bị từ chối, chi từ hạn mức còn lại được;
hết hạn mức → không gọi model; nối lại → đối soát đúng một lần.

Code và kiểm thử cục bộ không đồng nghĩa đã triển khai/chuyển sổ production.
