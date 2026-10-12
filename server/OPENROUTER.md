# OpenRouter trên server chính và dự phòng

Triển khai bản Worker mới lên **cả hai server** trước khi cấu hình. Dùng
`server/worker.js` với Wrangler, hoặc `work.js` nếu triển khai bằng Cloudflare Dashboard.
Git pull trên PC không tự triển khai Worker hay cập nhật APK.

Trên PC, vào **Cài đặt → Cấu hình máy và AI → Key AI trực tuyến**:

1. Đăng nhập quản trị viên của server chính.
2. Nhập key ở ô **OpenRouter**, chọn hoặc nhập mã model
   (ví dụ `openai/gpt-4.1-mini`, hoặc mã `:free` có trong danh sách).
3. Bấm **Kiểm tra OpenRouter**, rồi **Lưu key API**.
4. Vào **Cấu hình API dự phòng**, kiểm tra địa chỉ server đích,
   chọn **OpenRouter**, nhập key/model riêng, kiểm tra rồi lưu.
5. Chọn **OpenRouter** ở ô AI trên màn hình chat.

Android có lựa chọn OpenRouter trong chat và trang API dự phòng; cần APK mới.
Cấu hình server chính có thể thực hiện từ PC quản trị viên.

Key lưu mã hóa trong D1 của từng server, không tự sao chép sang server còn lại.
Để trống key khi chỉ đổi model. Chọn model chưa tự lưu; kiểm tra phản hồi
thành công rồi lưu để áp dụng. Model trên OpenRouter có khả năng ảnh/JSON và
giới hạn khác nhau; danh sách model không đồng nghĩa tất cả đều dùng được cho Agent.

Có thể dùng biến môi trường `OPENROUTER_MODEL` và secret `OPENROUTER_API_KEY`
thay cho cấu hình D1; cấu hình D1 đã lưu được ưu tiên.
Các endpoint cố định là `https://openrouter.ai/api/v1/models` và
`https://openrouter.ai/api/v1/chat/completions`.

Khi tính phí trong ứng dụng được bật, tài khoản thường bị chặn OpenRouter
với mã `OPENROUTER_PRICING_UNSET` vì chưa có bảng giá theo model.
Quản trị viên vẫn cấu hình, kiểm tra và sử dụng được; khi tính phí ứng dụng
tắt, tài khoản đã đăng nhập sử dụng theo key chung. Phí của OpenRouter vẫn
phụ thuộc model và tài khoản OpenRouter.

## Giảm độ trễ

Chat PC và Android dùng streaming cho NVIDIA/OpenRouter; Worker chuyển tiếp SSE
ngay khi nhận từng đoạn, không gom toàn bộ câu trả lời. Kế hoạch gọi công cụ
vẫn phải nhận đủ JSON hợp lệ trước khi thực thi.

OpenRouter gửi `provider: {sort: "latency", allow_fallbacks: true}` để ưu tiên
endpoint có độ trễ thấp và giữ dự phòng. NVIDIA gọi API trực tiếp, không gửi
tham số routing riêng của OpenRouter. Agent NVIDIA/OpenRouter dùng ngữ cảnh
rút gọn theo bước để giảm lượng input; yêu cầu nghiên cứu web giữ luồng đầy đủ.
Streaming giảm thời gian chờ hiển thị sau token đầu tiên, không đảm bảo model
miễn phí/hàng đợi sẽ sinh token đầu tiên nhanh hơn.
