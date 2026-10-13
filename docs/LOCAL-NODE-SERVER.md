# Server Node.js cá nhân cho API tùy chỉnh của Chat AI

Nguồn theo video: https://github.com/danieldev23/chatgpt-nodejs
Revision được ghim: `0835d0ddda312935c311393bc922dc690e54fac3`.
Đây là server bên thứ ba dùng phiên tài khoản ChatGPT, không phải OpenAI API
chính thức. Bộ cài không tự đăng nhập hoặc tự lấy token của trình duyệt.

## Cài trên Windows

Tại thư mục Chat AI chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\setup-local-node-server.ps1' -InstallNode -Start
```

Cần Git. Nếu thiếu Node.js, script dùng winget cài Node.js LTS. Nếu PATH
chưa nhận Node mới, mở lại PowerShell rồi chạy lại. Server cài vào
`%LOCALAPPDATA%\ChatAI\NodeServer`, không vào thư mục Google Drive của mã
Chat AI. Script ghim source, cài theo lockfile, build bằng `build:tsc`,
tạo `.env` với khóa ngẫu nhiên và chỉ nghe trên 127.0.0.1. Rerun không xóa
`.env` hoặc `data`. Có lối tắt `ChatAI Node Server` trên Desktop.

Giữ cửa sổ server mở; Ctrl+C dừng. Lần sau mở lối tắt, không cần cài lại.

## Kiểm tra và cấu hình

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\local-node-server.ps1' -Action Health
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\local-node-server.ps1' -Action CopyKey
```

CopyKey chỉ chép khóa server vào clipboard, không in ra log. Trong Chat AI
mở API tùy chỉnh dự phòng: URL `http://127.0.0.1:3040`, dán khóa server.
Đây không phải token phiên tài khoản.

## Thêm tài khoản của chính bạn

Theo hướng dẫn upstream, đăng nhập ChatGPT trong trình duyệt và mở
`https://chatgpt.com/api/auth/session`. Lấy giá trị `accessToken` rồi chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\local-node-server.ps1' -Action AddAccount
```

Nhập token tại prompt ẩn trên máy; không gửi token vào cuộc trò chuyện.
Thêm account thành công chưa xác minh upstream chat. Token có thể hết hạn
hoặc server upstream có thể từ chối; không dùng token của người khác.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\local-node-server.ps1' -Action Models
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\local-node-server.ps1' -Action Test -Model 'MODEL_THUC_TE'
```

Chọn model từ danh sách thực tế, nhập cùng model trong Chat AI, bấm Kiểm tra
chat rồi Lưu. `/health` không đủ chứng minh chat hoạt động. Không cần mở
cổng router, Docker hoặc Nginx khi chỉ dùng cùng máy.

## Đã xác minh / chưa xác minh

Source ghim đã cài dependencies theo lockfile, build TypeScript, khởi động
trên loopback và trả health. Endpoint accounts xác nhận auth bắt buộc.
Chưa chạy installer PowerShell trên Windows và chưa gọi upstream ChatGPT
với tài khoản của người dùng. Không tuyên bố chat đã hoạt động.
