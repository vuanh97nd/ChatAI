# API tùy chỉnh dự phòng trên Desktop

Mở menu **Cấu hình API dự phòng**, chọn **API tùy chỉnh / Node.js**.
Nếu chưa đăng nhập tài khoản backup Worker, mục cấu hình này mở trực tiếp.
Tính năng dành cho Desktop đang đăng nhập; không triển khai lại Worker.

* URL: `http://127.0.0.1:3040` cho server chạy cùng máy, hoặc URL HTTPS của VPS.
  Có thể nhập root URL, `/v1` hoặc đầy đủ `/v1/chat/completions`.
* Khóa: khóa Bearer xác thực server Node.js (`CHATGPT2API_AUTH_KEY` trong
  video), không phải accessToken của phiên ChatGPT.
* Model: model mà server và tài khoản phía server thực sự hỗ trợ. Không
  mặc định ví dụ `gpt-4o-mini` trong video là còn được hỗ trợ.
* Kiểm tra chat: một POST thật tới `/v1/chat/completions`, max_tokens=64;
  `/health` thành công không đủ. Kiểm tra không tự lưu cấu hình.
* Lưu cấu hình: dùng DPAPI của Windows và gắn với tài khoản/server chính.
  Không lưu khóa vào config.json, log hoặc Worker. URL đổi cần nhập lại khóa.
* Bật dự phòng: cho các lời gọi model/stream khi dịch vụ hiện tại lỗi mạng
  hoặc quá tải, trước khi đã nhận nội dung. Không dùng để vượt lỗi tài khoản,
  quyền, quota tính phí; không chuyển API lưu hội thoại sang server tùy chỉnh.
* **Dùng API này ngay**: gửi các yêu cầu chat/planning của ServerApiClient
  trực tiếp sang Node.js, không chờ Worker/NVIDIA báo quá tải. Bật và Lưu,
  sau đó bắt đầu yêu cầu mới. Chế độ này dùng model đã nhập trong cấu hình
  API tùy chỉnh, kể cả khi tên AI trong thanh chọn vẫn là nhà cung cấp cũ.
  Thanh trạng thái báo rõ đường gọi trực tiếp và model thực tế. Tắt ô này
  và Lưu để quay lại provider đã chọn; ô dự phòng độc lập vẫn có hiệu lực.

Sau lỗi provider đủ điều kiện, API tùy chỉnh được ưu tiên trước Worker
dự phòng nếu đã bật. Cấu hình DPAPI được tra bằng tài khoản/server chính,
không bị đổi scope khi client đã chuyển sang Worker dự phòng.

HTTP chỉ cho loopback. Remote dùng HTTPS; chuyển hướng bị từ chối để tránh
gửi khóa sai endpoint. Server phải trả JSON/SSE kiểu OpenAI. Stream bị ngắt
sau khi đã có nội dung không được tự phát lại yêu cầu.

Đây là đường gọi trực tiếp từ Desktop, tách biệt với cấu hình provider/key
trên Worker dự phòng. Chưa cấu hình hay kiểm tra VPS của người dùng.
