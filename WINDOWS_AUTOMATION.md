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

## Chrome tự động và DeepSeek trực tuyến

Cài lại `requirements-windows-automation.txt` để có **Playwright**, sau đó khởi động lại ChatAI. Dùng Chrome đã cài trên máy; không cần chạy `playwright install` hoặc bật cổng remote debugging. Trong **Cài đặt → Điều khiển ứng dụng**, bật quyền, thêm đúng `chrome.exe` (thường ở `C:\Program Files\Google\Chrome\Application\chrome.exe`) rồi Lưu. Tùy chọn **Chrome chạy nền** dùng headless; để tắt khi muốn quan sát cửa sổ.

Chọn **AI trực tuyến → DeepSeek API**, đăng nhập tài khoản đã được cấp DeepSeek trên server, rồi gửi riêng yêu cầu không kèm tệp/ảnh:

> Hãy mở Chrome và tìm kiếm thông tin về tiêu chuẩn 41-2022.

ChatAI đưa quy trình mở Chrome → truy vấn Bing → đọc text/URL vào một hộp duyệt. Đồng ý một lần để chạy toàn bộ quy trình; kết quả được gửi tới DeepSeek để tổng hợp. Công cụ `browser_search` có quyền truy cập Bing nằm trong preview, không cần bật nút Tìm web cho quy trình này. Bing thay cho Google vì Google có thể chặn profile tự động bằng CAPTCHA; Bing vẫn có thể chặn truy cập. Nếu gặp dấu hiệu CAPTCHA, công cụ báo `blocked` và AI chưa được coi là đã tìm thấy tài liệu. Phiên Chrome riêng đóng sau quy trình nên giải CAPTCHA trong Chrome thường rồi thử lại không giúp phiên này. Có thể dùng nút Tìm web (tra cứu trực tiếp bằng công cụ của ChatAI), hoặc cung cấp URL trang nguồn/PDF để đọc. Nếu số hiệu không đủ rõ hoặc trang lỗi, phải báo giới hạn. Nếu Chrome không có trong danh sách, thêm EXE và gửi lại yêu cầu.

`browser_run` hỗ trợ quy trình 1–12 bước **navigate → fill → click → read**. AI có thể mở trang, đọc các control/selector, đề nghị quy trình nhập/bấm, rồi đọc lại để kiểm tra kết quả. Mỗi quy trình cần duyệt toàn bộ trước khi chạy; AI không được chạy JavaScript/shell tùy ý. Quy trình được giới hạn khoảng 90 giây, mỗi thao tác có timeout riêng. Chỉ HTTPS công khai; chặn localhost/mạng riêng, download, popup và WebSocket. DNS thay đổi giữa lần kiểm tra và kết nối vẫn là giới hạn của cơ chế kiểm tra địa chỉ; không dùng tính năng như ranh giới mạng thay cho firewall.

Chrome dùng profile riêng không có cookie/tài khoản của trình duyệt thường và đóng sau mỗi quy trình. Không giữ phiên để đăng nhập hoặc xử lý luồng nhiều trang có trạng thái; quy trình sau phải mở trang lại. Không nhập ô mật khẩu, không vượt CAPTCHA, không xử lý UAC. Click có thể gửi biểu mẫu: hãy kiểm tra preview trước khi duyệt. Nội dung trang/app được gửi lên nhà cung cấp AI trực tuyến để xử lý.

DeepSeek, NVIDIA, Gemini và các AI trực tuyến qua proxy tương thích có thể lập kế hoạch bằng JSON cho cả công cụ Chrome và `windows_open`/`windows_inspect`/`windows_action`. ChatAI desktop thực hiện tại máy; server không tự truy cập máy Windows. Công cụ Windows vẫn duyệt từng bước, còn một quy trình Chrome chạy tự động sau một lần duyệt. Không cần Ollama cho luồng trực tuyến này. Cloudflare chat chưa hỗ trợ luồng điều khiển app. Cần kiểm thử API thật và Windows thật trên máy người dùng; test cloud dùng phản hồi nhà cung cấp giả lập.

**Dừng app AI** ở khung chat hoặc **Dừng điều khiển app** trong Cài đặt chặn các bước tiếp theo. Không cưỡng ép tắt app/tiến trình vì có thể mất tài liệu. Thao tác UIA đang thực hiện có thể cần hoàn tất. Bấm **Tiếp tục điều khiển app** trong Cài đặt để cấp lại quyền. Tắt quyền hoặc xóa EXE khỏi danh sách rồi lưu cũng chặn bước đang chờ duyệt. Phiên điều khiển không được giữ qua lần khởi động lại ChatAI.

## Tải PDF và mở Foxit Reader / PDF Editor

Hỗ trợ cả **Foxit PDF Editor** (`FoxitPDFEditor.exe`): thêm EXE Editor vào danh sách app được phép và dùng đường dẫn đó khi mở PDF. Chức năng này tải, đọc văn bản và mở file; chưa tự chỉnh sửa nội dung qua giao diện Editor.

Thêm EXE **Foxit PDF Reader** vào danh sách ứng dụng được phép và Lưu. Cài đặt thư mục được phép để lưu PDF (không lưu ngoài whitelist). Có thể gửi DeepSeek: “Tìm nguồn PDF chính thức của TCCS 41-2022, tải về, mở bằng Foxit Reader rồi đọc và tóm tắt.” AI tìm URL nguồn, đề nghị `pdf_source_open` để tải PDF tối đa 20 MiB, lưu một file mới và gửi lệnh mở Foxit. Đọc văn bản bằng thư viện PDF, không chụp/đọc màn hình Foxit; file scan cần OCR và không được coi là đã đọc toàn văn khi thiếu text. Dùng `pdf_read` và `next_start` để đọc tiếp phần còn lại; mỗi lượt đọc vẫn cần duyệt. Việc mở Foxit thành công không chứng minh tài liệu đúng số hiệu hoặc nội dung đã được kiểm chứng. Không ghi đè file, không hỗ trợ PDF mã hóa. Chrome vẫn chặn download; việc tải được thực hiện bởi công cụ PDF riêng với preview URL và đường dẫn đích.

## Phạm vi hỗ trợ

Với UIA: chỉ Windows desktop đang đăng nhập, app cung cấp control UIA chuẩn và cửa sổ thuộc chính tiến trình đã mở. Có thể hiện cửa sổ hoặc hộp thoại; không bảo đảm chạy ngầm. App single-instance chuyển yêu cầu sang tiến trình có sẵn, launcher mở tiến trình con, UWP, game, cửa sổ quản trị/UAC hoặc giao diện custom có thể chưa được hỗ trợ. Chrome dùng công cụ Playwright riêng ở trên để tránh giới hạn single-instance. Chưa có click theo tọa độ, phím tắt toàn hệ thống, OCR màn hình hoặc điều khiển ứng dụng tùy ý qua hình ảnh.

Công cụ không tự sao lưu dữ liệu của app bên ngoài. Trước khi duyệt nút gửi/lưu/xóa/đóng, kiểm tra mục tiêu và nội dung. Thử với app/tài liệu thử nghiệm trước. Tài liệu trong app có thể xuất hiện trong lịch sử ChatAI khi bạn duyệt đọc giao diện. Không dùng công cụ để nhập mật khẩu.

Các test tự động kiểm tra danh sách được phép, xác nhận, hash EXE, phiên theo tài khoản, PID, control thay đổi, mật khẩu, thu hồi quyền và nút dừng bằng backend giả lập. Môi trường cloud Linux không kiểm thử được pywinauto hay thao tác app Windows thật; cần thử trên Windows trước khi dùng với dữ liệu thật.
