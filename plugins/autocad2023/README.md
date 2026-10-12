# Chat AI trong AutoCAD 2023 — bản thử 0.1

Plugin Windows x64/.NET Framework 4.8, bảng WinForms PaletteSet, lệnh `CHATAI`.
Chưa biên dịch hoặc chạy AutoCAD thực trong môi trường Linux phát triển.

## Cài trên Windows

1. Đóng AutoCAD 2023. Cập nhật mã nguồn ChatAI (`git pull --rebase origin main`).
2. Mở PowerShell tại thư mục mã nguồn, chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\plugins\autocad2023\install.ps1
```

Bypass chỉ áp dụng tiến trình chạy script này, không đổi chính sách máy.
Nếu AutoCAD ở ổ khác, thêm `-AutoCADPath 'D:\Autodesk\AutoCAD 2023'`.
Script dùng compiler Windows và thư viện của bản AutoCAD đã cài, không tải DLL Autodesk.
Script không ghi đè plugin cũ. DLL được biên dịch vào `build`; bundle cài tại
`%APPDATA%\Autodesk\ApplicationPlugins\ChatAI2023.bundle`.

3. Mở AutoCAD, gõ `CHATAI`. Nếu chưa tự nạp, dùng `NETLOAD` chọn DLL trong bundle.
   Nếu AutoCAD hỏi tin cậy, kiểm tra đúng DLL vừa tạo rồi duyệt theo chính sách máy;
   không tắt SECURELOAD. Không hỗ trợ AutoCAD LT 2023.
4. Đăng nhập server mặc định dự phòng hoặc nhập địa chỉ server HTTPS khác.
   Plugin dùng phiên companion của API hiện có, không lưu mật khẩu/token ra file.

## Thử trên bản vẽ mới

- Chat: “Giải thích cách ghi kích thước trong AutoCAD”.
- Vẽ: “Đơn vị bản vẽ mm. Vẽ đường thẳng WCS từ (0,0,0) tới (1000,0,0)”.
- Vẽ: “Đơn vị bản vẽ mm. Vẽ đường tròn WCS tâm (500,500,0), bán kính 200”.
- Xem JSON trả về, bấm **Duyệt và vẽ JSON**. Đếm đối tượng, kiểm tra tọa độ;
  thử `U`/Undo sau mỗi nhóm trên bản vẽ thử. Plugin không tự lưu.
- Chọn đối tượng trước khi mở bảng; bật ô gửi thông tin để AI nhận tối đa 100
  handle/type/layer, tên file (không có đường dẫn) và đơn vị. Không gửi toàn bộ DWG.

## Giới hạn

Mỗi câu hỏi độc lập; chưa đồng bộ bộ nhớ/lịch sử ChatAI. Chỉ thực thi JSON line/circle,
tối đa 100 thao tác trong một transaction; lỗi làm hủy cả nhóm. Không chạy mã LISP,
shell hoặc JSON công cụ khác. Chưa sửa/xóa đối tượng, polyline, block, dimension.
Giao diện chờ API bất đồng bộ, không tự thử lại thao tác vẽ. Lỗi hiện trong bảng;
không ghi log chứa mật khẩu hoặc dữ liệu bản vẽ.

Gỡ thử: đóng AutoCAD rồi đổi tên/di chuyển bundle ra khỏi ApplicationPlugins.
