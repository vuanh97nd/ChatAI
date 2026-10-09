# Bộ nhớ cách làm và đào tạo dùng chung

ChatAI lưu bài học theo từng bước công cụ: tham số đã lọc khóa, lỗi nhận được, môi trường/phần mềm, mức kiểm chứng và liên kết tới bước sửa thành công. Bài học vẫn là dữ liệu tham khảo; ứng dụng không chạy lại lệnh hoặc lấy thông số công trình cũ làm đầu vào của bài mới.

## Đào tạo bằng admin

1. Cập nhật desktop và Worker. Đăng nhập admin.
2. Mở **Tài khoản → Bộ nhớ đào tạo AI**, bật **Đào tạo AI · chia sẻ bài học mới**. Có thể bật/tắt ngay trong menu tài khoản.
3. Yêu cầu AI thực hiện bài mẫu. Các kết quả công cụ và lỗi kiểm tra tham số mới được ghi lại; lời nói “đã thành công” của AI không phải bằng chứng.
4. Bài học mới trong chế độ đào tạo được đồng bộ vào kho chung, lọc khóa và thông tin đường dẫn, thay nội dung yêu cầu riêng bằng mô tả công cụ. Người dùng khác nhận kho chung khi đăng nhập và qua đồng bộ nền mỗi 15 giây.
5. Admin xem các bản ghi theo trang trong **Bộ nhớ đào tạo AI**. Nếu bài học không còn phù hợp, chọn **Thu hồi bài học đã chọn**. Máy khác nhận dấu thu hồi ở lần đồng bộ tiếp theo.

Tắt chế độ đào tạo để công việc tiếp theo chỉ ghi vào kho riêng. Bật đào tạo không tự công bố toàn bộ lịch sử cũ. Chỉ server đã xác thực quyền admin mới được ghi/thu hồi bài học chung; tài khoản thường không thể tự khai báo mình là admin trong dữ liệu gửi lên.

## Sáu thay đổi

- **Ghi nhớ lỗi:** lưu kết quả lỗi xác định và lỗi kiểm tra tham số. Với một nhóm lệnh chạy dở, lưu riêng những lệnh đã thực hiện và bước chưa rõ; không coi bước chưa rõ là chưa chạy.
- **Liên kết cách sửa:** một thao tác thành công liên kết các lỗi trước của cùng thao tác/đối tượng và môi trường trong tiến độ công việc. Liên kết xác nhận bước được sửa, không chứng minh toàn bài đã đúng.
- **Tra trước thao tác:** so sánh lệnh định thực hiện với kho riêng và kho chung. Lỗi xác định có cách sửa, cùng phiên bản, được nhắc đổi cách xử lý trước khi chạy. Lỗi mạng hoặc phiên bản chưa xác định chỉ tham khảo; không cấm thử lại hợp lý. Lệnh giống hệt đã lỗi hai lần trong cùng lượt vẫn bị chặn.
- **Nhớ tiến độ:** ghi đối tượng, bước đã áp dụng, bước đọc, bước lỗi và bước chưa rõ. Hội thoại đồng bộ mang checkpoint nhưng không khôi phục hàng đợi hay tự chạy. Phải đọc trạng thái mô hình thật trước khi tiếp tục/tạo lại. Lệnh tạo project mới thành công đặt lại tiến độ mô hình đang theo dõi.
- **Kho server riêng:** bảng `ai_lessons` không áp quota tổng số bản ghi. Upload tối đa 10 bản ghi/đợt, tải 50 bản ghi/trang; các giới hạn này chỉ kiểm soát mỗi yêu cầu. Kho trên máy và server không cắt ở 20/100 bản ghi như trước. Snapshot hội thoại tương thích bản cũ vẫn chỉ chứa 20 ví dụ, còn API riêng đồng bộ đầy đủ. Không đưa toàn bộ kho vào một prompt: tìm phần liên quan và giữ ngân sách ngữ cảnh.
- **Mức kiểm chứng:** `command` = bước lệnh được công cụ xác nhận; `model` = các thuộc tính mô hình được đối chiếu; `results` = đã đọc kết quả số với trạng thái tính toán được xác nhận. Đây không phải chứng nhận thiết kế. `verify_model` kiểm tra đúng các thuộc tính/điều kiện được liệt kê; không mặc nhiên xác nhận toàn bộ hình học hay mọi giả thiết.

PLAXIS có thể nhận diện phiên bản file thực thi của tiến trình đang nghe cổng scripting trên Windows. Khi không đọc được metadata/quyền tiến trình, đánh dấu phiên bản chưa rõ thay vì đoán. GeoStudio hoặc công cụ khác có thể cung cấp trường `environment` từ kết quả thực thi; nếu không có thì giữ `unknown`.

## Server và đồng bộ

- `POST /api/lessons/put`: ghi kho riêng; `scope=shared` chỉ admin.
- `POST /api/lessons/list`: cursor tăng, trả kho riêng của tài khoản và kho chung.
- `POST /api/lessons/search`: tìm trong hai kho được phép đọc.
- `POST /api/admin/lessons/withdraw`: thu hồi bài học chung.

Schema tự tạo trên D1 khi dùng API. Dữ liệu đồng bộ lỗi/mất mạng được giữ trên SQLite để gửi lại; lỗi đồng bộ không chặn AI hay khóa giao diện. Không áp giới hạn tổng số bản ghi trong ứng dụng; dung lượng thực tế phụ thuộc tài nguyên SQLite/D1 và gói lưu trữ.

Bộ nhớ này bổ sung dữ kiện vào ngữ cảnh và kiểm tra công cụ, không huấn luyện lại trọng số DeepSeek. Chưa xác minh bằng một bài chạy thật trên máy Windows thì không báo đã chạy PLAXIS/GeoStudio thành công.
