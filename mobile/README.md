# ChatAI Android — bản thử nghiệm 0.8

Ứng dụng Flutter Android 6.0+ dùng server ChatAI hiện có. Mặc định NVIDIA;
DeepSeek tính phí theo bảng giá server. Không đưa API key nhà cung cấp vào APK.

## Chức năng bản này

- Đăng nhập bằng email/tên tài khoản; đăng ký bắt buộc email, tự đăng nhập.
- Giữ phiên trong Android Keystore qua flutter_secure_storage; xóa khi đăng xuất.
- Chat NVIDIA/DeepSeek; lưu và mở lại hội thoại trên server.
- Đọc/thêm bộ nhớ cá nhân và đọc thông báo Admin.
- Số dư, token theo tháng, phí duy trì theo cấu hình server; nhập số tiền QR
  20.000–10.000.000 đ, bội số 1.000 đ. Admin không hiện nút nạp.
- Chỉ kiểm tra đơn QR đang mở mỗi 10 giây; lùi đến 60 giây khi lỗi,
  ngừng khi ứng dụng xuống nền, khi hết hạn hoặc đã thanh toán.
- Micro nhập câu hỏi tiếng Việt: hiển thị bản nháp, người dùng kiểm tra và bấm gửi.
- Nút Đọc câu trả lời / Dừng đọc; tự dừng nghe/đọc khi xuống nền, đổi trang hoặc đăng xuất.
- Mục Máy tính: quét/dán QR, chờ Windows cấp quyền, gửi việc bằng chữ/giọng nói,
  xem tiến trình/kết quả văn bản, tạm dừng/tiếp tục/hủy, bổ sung cho AI.
- Yêu cầu ảnh màn hình Windows khi máy tính đã bật quyền riêng; phóng to ảnh,
  ẩn ảnh, tự hết hạn sau 5 phút. Không chụp định kỳ hoặc tự gửi ảnh cho AI.

Chưa có gửi PDF/Excel/DXF trực tiếp lên Windows, tải file kết quả, push notification,
đồng bộ hội thoại desktop hay tự cập nhật APK. Kho hội thoại Android hiện là
`ai_conversations`; desktop đang dùng `desktop_history`. Bộ nhớ cá nhân và ví dùng chung.
Đăng nhập Android gửi `client_type=android_companion`, được cấp phiên riêng và
không thay thế khóa thiết bị desktop. Quyền điều khiển máy chỉ có sau khi Windows
xác nhận QR. Cần triển khai Worker mới để dùng luồng đồng hành này.

## Tải APK thử nghiệm

GitHub → Actions → **Build Android APK** → chọn lượt chạy xanh → Artifacts →
**ChatAI-Android-test-…** → tải ZIP, giải nén `app-debug.apk`, chuyển sang điện thoại.
Cho phép trình duyệt/trình quản lý file cài ứng dụng từ nguồn này. Đây là APK debug
cho thử nghiệm; không dùng để phát hành chính thức. Máy cài có thể hiện cảnh báo.
APK debug giữa các máy build có thể khác khóa: khi bị lỗi chữ ký phải gỡ bản thử
nghiệm cũ; phát hành chính thức cần khóa ký cố định như bên dưới.

## Build tại máy

Cài Flutter 3.35.7 và Android Studio + Android SDK; chạy `flutter doctor` và xử lý
mục Android toolchain. Python dùng để chuẩn bị cấu hình Android.

```powershell
cd mobile
python tool/prepare_android.py
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

File: `mobile/build/app/outputs/flutter-apk/app-debug.apk`.
Script lấy cấu trúc Android từ chính phiên bản Flutter đang dùng; không ghi đè
mã ứng dụng và kiểm thử. Cần triển khai Worker mới cho mục Máy tính; chat/giọng nói dùng API sẵn có.

## Ký APK chính thức

Tạo một keystore riêng, sao lưu an toàn. Không commit keystore/mật khẩu.

```powershell
keytool -genkeypair -v -keystore chatai-release.jks -alias chatai -keyalg RSA -keysize 2048 -validity 10000
$env:ANDROID_KEYSTORE = (Resolve-Path .\chatai-release.jks).Path
$env:ANDROID_KEY_ALIAS = "chatai"
# Thiết lập ANDROID_STORE_PASSWORD và ANDROID_KEY_PASSWORD trong môi trường an toàn.
flutter build apk --release
```

Luôn giữ cùng keystore để cập nhật. Script không dùng khóa debug thay cho khóa
release. Thay endpoint khi build: `--dart-define=CHAT_AI_SERVER=https://...`;
chỉ hỗ trợ HTTPS. Không lưu key nhà cung cấp hoặc thông tin ngân hàng trong app.

## Kiểm tra trên điện thoại trước phát hành

Đăng ký → tự đăng nhập → đóng/mở app → chat NVIDIA → chọn DeepSeek → kiểm tra
số dư/thiếu số dư → tạo QR và chuyển khoản thử → đổi nền/mở lại → xác nhận paid
chỉ cộng tiền một lần → xem bộ nhớ → đăng xuất và đăng nhập tài khoản khác.
Kiểm tra thêm mạng mất, server trả lỗi, bàn phím, xoay màn hình và chữ lớn.
Không coi kiểm thử giả lập HTTP là xác nhận thanh toán thật.

## Giọng nói

Lần đầu bấm micro, Android hỏi quyền ghi âm. Nếu từ chối, vẫn nhập chữ bình thường;
có thể bật lại trong Cài đặt Android → Ứng dụng → Chat AI → Quyền → Micro.
Máy cần dịch vụ nhận dạng hỗ trợ tiếng Việt (ví dụ Speech Services by Google);
nhận dạng có thể cần mạng và có thể gửi âm thanh đến dịch vụ do Android lựa chọn.
ChatAI không tải âm thanh lên server ChatAI hoặc lưu bản ghi âm; chỉ gửi văn bản
sau khi bạn bấm Gửi. Chức năng đọc cần giọng tiếng Việt trong cài đặt Text-to-speech
của Android. Đây là hội thoại bằng nút bấm, chưa phải gọi thoại liên tục.

Thử thêm: từ chối quyền → nhập chữ; cấp quyền → nói → chỉnh bản nháp → gửi;
đọc câu trả lời dài → dừng; chuyển app xuống nền khi đang nghe/đọc;
thiếu dịch vụ nhận dạng hoặc thiếu giọng Việt phải hiện thông báo thay vì treo app.

## Kết nối Windows

1. Cập nhật và mở ChatAI Windows, đăng nhập cùng tài khoản Android.
2. Menu Tài khoản → Kết nối điện thoại (hoặc Cài đặt → Nâng cao).
3. Android → Máy tính → Quét QR hoặc Dán mã. Windows xác nhận tên điện thoại.
4. Gửi việc. Nếu máy offline, chưa cho phép nhận việc hoặc đang có tác vụ/bản nháp
   cục bộ, yêu cầu chờ trong hàng đợi. ChatAI Windows phải đang mở và có mạng.
5. Tạm dừng/hủy là yêu cầu dừng tại điểm an toàn, không bảo đảm ngắt ngay phần mềm
   đang tính. Mất kết nối không tự chạy lại tác vụ đã nhận. Kết quả chưa rõ cần kiểm tra.
6. Windows có nút thu hồi điện thoại và ngừng nhận việc mới. AI dùng quyền, model,
   thư mục hiện có trong cấu hình Windows; chức năng này không cấp quyền ngoài cấu hình.

Bản này trả văn bản kết quả; đọc file đã có trong thư mục Windows qua câu lệnh.
Chưa chuyển file từ điện thoại, tải file kết quả hoặc điều khiển chuột/phím trực tiếp.
Nếu PLAXIS Input đang mở, tác vụ có tên PLAXIS bị từ chối trước khi chạy để tránh
thay thế mô hình hiện tại. Chuẩn bị project riêng trên Windows trước.

## Admin trên Android

Tài khoản → Quản trị (chỉ hiện với Admin). Có tìm/lọc/phân trang người dùng,
token tháng hiện tại theo giờ Việt Nam, số dư, chi tiết token các tháng và nhật ký
quản trị; khóa/mở khóa, thu hồi phiên, xóa mềm/khôi phục trong thời hạn server.
Tab Thông báo gửi tất cả (*) hoặc một tên tài khoản. Tab Thanh toán nạp thủ công
1.000–5.000.000 đ có lý do và sửa phí duy trì (cho phép 0 đ), giá DeepSeek.

Nạp tiền/thông báo lưu mã yêu cầu trong Keystore trước gửi. Khi mất mạng, thử lại
đúng nội dung dùng cùng mã. Yêu cầu chưa xác minh được khôi phục khi mở lại trang;
không tự gửi lại. Server kiểm tra quyền Admin trên mọi endpoint. Không dùng
admin-key trong APK, không thay đổi cơ chế tự xác nhận QR.

Phạm vi hiện tại chưa có cấu hình ngân hàng/webhook, email/Resend, key nhà cung cấp
AI hoặc đào tạo bộ nhớ chung từ Android. Các chức năng đó vẫn quản lý trên desktop.
Trước phát hành: thử tài khoản thường không thấy/truy cập được quản trị; kiểm tra
nạp mất mạng không cộng hai lần, khóa/khôi phục, thông báo và giá 0 đ trên máy thật.

## Logo và khởi động

Logo robot dùng chung bản Windows, đóng gói trong assets/chat_ai.png. Script
prepare_android tạo icon thường, adaptive icon (Android 8+) và splash nền tối
cho cả giao diện sáng/tối, bao gồm Android 12+. Khi Flutter đã mở mà còn đang
khôi phục đăng nhập, hiện logo, tên Chat AI và chỉ báo tải, không trì hoãn cố định.
Cần build APK mới để đổi icon/splash; cập nhật source không đổi APK đã cài.

## Dùng thử không đăng nhập

Mở thẳng màn hình Chat; mỗi mã thiết bị lưu trong Keystore có 3 lượt gửi tin nhắn
NVIDIA, từ lượt tiếp theo yêu cầu đăng nhập/đăng ký. Lượt đã gửi đến dịch vụ, kể cả
lỗi hoặc mất phản hồi, vẫn tính để tránh chạy lại tốn API. Thử lại cùng mã/nội dung
chỉ đọc phản hồi đã lưu, không gọi nhà cung cấp lần hai. Chưa đăng nhập không dùng
DeepSeek, ví, bộ nhớ, Admin hay điều khiển máy tính. Tin nhắn khách hiển thị trong
phiên hiện tại, không tự nhập vào lịch sử tài khoản sau đăng nhập.

Giới hạn theo mã lưu của bản cài, không phải nhận dạng phần cứng chống giả mạo;
xóa dữ liệu/cài lại có thể tạo mã khác. Server còn giới hạn tần suất theo IP.
Cần Worker và APK mới để dùng. Chưa có thông báo đẩy ngoài ứng dụng.

## Thông báo và quyền Android

Tài khoản → Bật thông báo điện thoại: xin POST_NOTIFICATIONS trên Android 13+,
tạo kênh Thông báo ChatAI và đăng ký kiểm tra nền bằng WorkManager (khoảng 15 phút,
cần mạng). Android có thể trì hoãn vì tiết kiệm pin; không phải push tức thời FCM.
Tắt trong app hủy công việc nền; đăng xuất cũng hủy và xóa thông báo đang hiện.
Không đọc nội dung của tài khoản khác, không tự gửi thông báo cũ ngay khi bật.
Mở app/làm mới sẽ kiểm tra thêm; người dùng vẫn đọc toàn bộ trong Bộ nhớ.

Quyền cần thiết: Internet, Micro khi bấm nói, Camera khi quét QR, Thông báo khi
bấm bật. Không yêu cầu đọc toàn bộ bộ nhớ máy hoặc trợ năng để điều khiển Windows.
Chế độ khách không đăng ký nhận thông báo tài khoản. Cần thử trên Android thật:
cấp/từ chối quyền, tài khoản khác, logout, nền/khởi động lại, tiết kiệm pin.

WorkManager được cố định 0.9.0 cùng ba module nền tảng vì bản 0.9.4 có chữ ký
Apple không khớp platform interface, làm kiểm thử Dart trên Android không biên dịch.
Không nâng riêng một module; chạy lại analyze, test và build APK khi nâng cả bộ.
