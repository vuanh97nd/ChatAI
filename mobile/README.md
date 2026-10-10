# ChatAI Android — bản thử nghiệm 0.2

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
- Không điều khiển hoặc ghi đè mô hình PLAXIS/GeoStudio.

Chưa có đọc PDF/Excel/ảnh, push notification, chạy tác vụ Windows,
đồng bộ hội thoại desktop hay tự cập nhật APK. Kho hội thoại Android hiện là
`ai_conversations`; desktop đang dùng `desktop_history`. Bộ nhớ cá nhân và ví dùng chung.
Server hiện khóa một thiết bị cho mỗi tài khoản thường: đăng nhập Android có thể
ảnh hưởng phiên desktop; không thay đổi chính sách này trong bản Android đầu tiên.

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
mã ứng dụng và kiểm thử. Không cần cập nhật Worker cho bản này.

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
