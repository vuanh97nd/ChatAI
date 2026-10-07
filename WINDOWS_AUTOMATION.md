# Điều khiển ứng dụng Windows

Trong **Cài đặt → Điều khiển ứng dụng**, bật quyền, chọn **Thêm ứng dụng EXE…**, chọn tệp thực thi rồi **Lưu cài đặt**. Mặc định tắt; chỉ app trong danh sách được mở. Không cần quyền quản trị. Không chạy ChatAI bằng Administrator để vượt qua UAC.

Cài thư viện tùy chọn bằng PowerShell tại thư mục dự án, cùng môi trường Python dùng chạy ChatAI:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-windows-automation.txt
```

Đóng/mở lại ChatAI sau cài. Chọn Qwen2.5 7B local và **Dùng công cụ AI tự động trong chat**. Ví dụ: “Mở ứng dụng đã được phép ở đường dẫn C:\Apps\Demo.exe, đọc giao diện, bấm nút Run test và báo kết quả nhìn thấy.” Bạn phải duyệt từng bước, kể cả đọc giao diện vì dữ liệu đó được đưa vào hội thoại.

## Các bước AI có thể thực hiện

- `windows_open`: mở EXE đã cho phép, không nhận arguments, shell hoặc script. Trả ID phiên ứng dụng.
- `windows_inspect`: đọc tối đa 60 control UI Automation của tiến trình vừa mở, bỏ ô mật khẩu và control của tiến trình khác. Không đọc ảnh toàn màn hình. Trả token control mới cho bước tiếp theo.
- `windows_action`: bấm nút qua InvokePattern, nhập vào ô Edit bằng ValuePattern, hoặc đóng cửa sổ được chọn. Mỗi lần đều cần xác nhận. Sau thao tác phải đọc lại để kiểm tra kết quả; việc gửi thao tác thành công không chứng minh bài test của app đã đạt.

**Dừng app AI** ở khung chat hoặc **Dừng điều khiển app** trong Cài đặt chặn các bước tiếp theo. Không cưỡng ép tắt app/tiến trình vì có thể mất tài liệu. Thao tác UIA đang thực hiện có thể cần hoàn tất. Bấm **Tiếp tục điều khiển app** trong Cài đặt để cấp lại quyền. Tắt quyền hoặc xóa EXE khỏi danh sách rồi lưu cũng chặn bước đang chờ duyệt. Phiên điều khiển không được giữ qua lần khởi động lại ChatAI.

## Phạm vi hỗ trợ

Chỉ Windows desktop đang đăng nhập, app cung cấp control UIA chuẩn và cửa sổ thuộc chính tiến trình đã mở. Có thể hiện cửa sổ hoặc hộp thoại; không bảo đảm chạy ngầm. App single-instance chuyển yêu cầu sang tiến trình có sẵn, launcher mở tiến trình con, UWP, game, cửa sổ quản trị/UAC hoặc giao diện custom có thể chưa được hỗ trợ. Chưa có click theo tọa độ, phím tắt toàn hệ thống, OCR màn hình, điều khiển Chrome headless hoặc điều khiển ứng dụng tùy ý qua hình ảnh.

Công cụ không tự sao lưu dữ liệu của app bên ngoài. Trước khi duyệt nút gửi/lưu/xóa/đóng, kiểm tra mục tiêu và nội dung. Thử với app/tài liệu thử nghiệm trước. Tài liệu trong app có thể xuất hiện trong lịch sử ChatAI khi bạn duyệt đọc giao diện. Không dùng công cụ để nhập mật khẩu.

Các test tự động kiểm tra danh sách được phép, xác nhận, hash EXE, phiên theo tài khoản, PID, control thay đổi, mật khẩu, thu hồi quyền và nút dừng bằng backend giả lập. Môi trường cloud Linux không kiểm thử được pywinauto hay thao tác app Windows thật; cần thử trên Windows trước khi dùng với dữ liệu thật.
