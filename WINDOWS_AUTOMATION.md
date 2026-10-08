# Điều khiển ứng dụng Windows

Trong **Cài đặt → Điều khiển ứng dụng**, bật quyền, chọn **Thêm ứng dụng EXE…**, chọn tệp thực thi rồi **Lưu cài đặt**. Mặc định tắt; chỉ app trong danh sách được mở. Không cần quyền quản trị. Không chạy ChatAI bằng Administrator để vượt qua UAC.

Hai quyền tùy chọn, mặc định tắt:

- **Tự cài thư viện cần thiết đã được kiểm tra**: khi dùng công cụ app, ChatAI phát hiện thư viện thiếu và dùng đúng `python.exe` của tiến trình đang chạy để cài các gói cố định pywinauto, psutil, comtypes, Playwright, pypdf, python-docx và ezdxf. Áp dụng virtualenv hoặc runtime đóng gói có marker; không cài vào Python hệ thống, không nâng quyền và model không được chọn gói/index/lệnh tùy ý. Có trạng thái tiến trình, giới hạn 4 phút; Dừng AI hoặc thu hồi quyền sẽ ngắt cài. Nếu cài xong mà chưa nạp được, cần khởi động lại app. Mạng/pip bị lỗi sẽ được báo; không bảo đảm mọi thiếu sót runtime có thể tự sửa.
- **Cho phép mở mọi ứng dụng đã cài**: công cụ `windows_list_apps` tra EXE đăng ký trong Windows App Paths và thông tin DisplayIcon của phần mềm đã cài. EXE trong danh sách đó được mở ngoài danh sách thủ công; đường dẫn không được phát hiện vẫn bị chặn. App portable, UWP hoặc app không đăng ký EXE cần thêm thủ công và có thể không hỗ trợ UIA. Không tự nâng quyền quản trị, không cho phép shell/script host hoặc trình gỡ cài đặt thông dụng. Danh sách ứng dụng được gửi cho AI chỉ sau khi duyệt. Quyền mở không bỏ xác nhận đọc/bấm/nhập/gửi/lưu/xóa; mỗi quy trình vẫn cần duyệt như trước. Tắt quyền rồi lưu chặn bước mở tiếp theo và các phiên không còn được phép.

Hai quyền áp dụng cả AI trên máy và AI trực tuyến qua ChatAI desktop. Muốn dùng, bật quyền điều khiển app cùng các tùy chọn này rồi **Lưu**; thư viện được kiểm tra khi bạn gửi yêu cầu tiếp theo, không cài ngay khi đánh dấu checkbox.

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

### Nhận diện ứng dụng và tiếp nối yêu cầu

Khi yêu cầu mở ứng dụng (Word, Excel, Photoshop hoặc app khác), ChatAI đưa bước `windows_list_apps` vào luồng duyệt trước khi model lập kế hoạch mở. Quyền mở mọi ứng dụng đăng ký Windows được mô tả riêng với danh sách EXE thêm thủ công; danh sách thủ công không giới hạn quyền này. Các bước mở và thao tác vẫn kiểm tra quyền hiện tại và cần duyệt.

Trong cuộc trò chuyện điều khiển app trực tuyến, câu trả lời bổ sung như tên bài hát tiếp tục được gửi tới bộ lập kế hoạch công cụ khi quyền điều khiển còn bật. Tạo cuộc trò chuyện mới để quay về chat thường. Không bảo đảm mọi app hỗ trợ UI Automation; Word có thể không cung cấp ô Edit để nhập nội dung. Phiên browser_run hiện đóng sau quy trình nên chưa hỗ trợ duy trì phát nhạc.

### Quyền một lần và viết tài liệu Word

Trong Cài đặt → Điều khiển ứng dụng, bật **Tự thực hiện yêu cầu điều khiển app, không hỏi lại từng bước** rồi Lưu. Quyền này mặc định tắt; khi bật cùng quyền điều khiển ứng dụng, các công cụ Windows, Chrome, PDF và tạo DOCX/mở Word tự thực hiện yêu cầu trong cả luồng local và trực tuyến. Các công cụ xóa file, chạy lệnh và sửa tài liệu khác vẫn theo quyền riêng. Tắt quyền hoặc bấm Dừng để ngắt các bước tiếp theo. Không tự chạy lại thao tác bị ngắt có kết quả chưa rõ.

`word_create_open` tạo DOCX mới trong thư mục được phép từ nội dung AI soạn, sau đó mở bằng WINWORD.EXE được phép. Không ghi đè tài liệu đang có; không thao tác vùng soạn thảo Word bằng phím toàn hệ thống. Kết quả phân biệt tài liệu đã tạo với lệnh mở Word đã gửi; chưa xác minh cửa sổ Word thực tế.

### Thanh điều khiển khi AI làm việc

Tùy chọn **Tự thu gọn chat khi AI điều khiển ứng dụng** mặc định bật. Khi bắt đầu công cụ ứng dụng, chat thu nhỏ và thanh nổi luôn trên cùng hiện trạng thái, thời gian chạy, **Tạm dừng / Tiếp tục**, **Mở chat** và **Kết thúc**. Kéo phần nền thanh để đổi vị trí; vị trí được lưu riêng trên máy.

Tạm dừng giữ tác vụ và chờ ở lần kiểm tra quyền tiếp theo, không cưỡng ép dừng thao tác native đang chạy. Tiếp tục gỡ trạng thái tạm dừng. Kết thúc chặn các bước sau và hủy lượt chat, không đóng Word/Chrome bên ngoài hoặc xóa tài liệu. Mở chat chỉ hiện cửa sổ chính để theo dõi. Khi tác vụ xong, lỗi hoặc cần duyệt thủ công, chat tự hiện lại và thanh nổi đóng.

Quyền điều khiển app cũng có thể lưu từ hộp thoại Đồng ý đầu tiên: giữ chọn **Ghi nhớ quyền điều khiển app, không hỏi lại sau mỗi bước hoặc lỗi**. Quyền được lưu vào cấu hình, giữ qua lần khởi động lại và có thể tắt trong Cài đặt. Khi quyền này đã bật, thao tác bị ngắt chưa rõ kết quả được ghi nhận mà không hỏi lại và không tự thực hiện lại.

### Vẽ bản CAD mới

Công cụ `cad_create_open` hỗ trợ AI local và trực tuyến: tạo DXF mới trong thư mục được phép rồi mở bằng AutoCAD (`acad.exe`) hoặc AutoCAD LT (`acadlt.exe`) được phép. Hỗ trợ đường tròn, đoạn thẳng, hình chữ nhật; đơn vị mm/cm/m/inch. Thiếu kích thước hoặc đơn vị thì AI hỏi thông số, không hỏi lại quyền đã lưu. Thư viện ezdxf được tự cài theo quyền cài gói hiện có.

Ví dụ: **Vẽ trong AutoCAD đường tròn tâm (0,0), bán kính 50 mm** hoặc **Vẽ hình chữ nhật rộng 200 mm, cao 100 mm tại (0,0)**. Kết quả gồm đường dẫn DXF và trạng thái gửi lệnh mở; chưa xác minh cửa sổ AutoCAD. Không sửa DWG đang mở, không chạy AutoLISP/script, không ghi đè tệp cũ.

Nhận diện AutoCAD hỗ trợ tên EXE acad.exe/acadlt.exe và InstallLocation trong mục đăng ký gỡ cài đặt khi DisplayIcon không chỉ tới app. Nếu bản portable không đăng ký, thêm đường dẫn EXE thực tế thủ công.

Trước bước công cụ app đầu tiên của mỗi yêu cầu mới, chat hiện đếm ngược 3–2–1 giây và nút **Hủy yêu cầu**. Hủy trong khoảng này ngăn công cụ được thực hiện. Các bước sau hoặc tiếp tục duyệt trong cùng yêu cầu không đếm ngược lại.

Trong mục Gần đây, hội thoại đang chọn có nút thùng rác ngay bên phải; các dòng khác có menu đổi tên/xóa. Sau khi xóa, nút **Hoàn tác** xuất hiện 5 giây. Hội thoại được backup trước khi xóa; hoàn tác khôi phục lịch sử và tên, không ghi đè hội thoại đã tồn tại. File Word/PDF/DXF đã tạo không bị xóa.

Nút **Dừng app AI** hủy lượt hiện tại và chặn các bước tiếp theo. Khi đang chờ API model, bộ lập kế hoạch dừng mà không chờ phản hồi mạng; phản hồi tới muộn bị bỏ qua và không được dùng để chạy công cụ. Yêu cầu HTTP đã gửi có thể vẫn xử lý phía dịch vụ đến khi hết timeout. Nút đóng cửa sổ khi tác vụ có thể hủy sẽ yêu cầu dừng rồi tự thoát khi worker kết thúc, không đóng AutoCAD/Word ngoài ChatAI. I/O Windows hoặc Google Drive đang bị chặn vẫn có thể cần đợi hệ điều hành trả về.

### Giảm thời gian chờ đăng nhập và lập kế hoạch

Đăng nhập hoàn tất ngay sau xác thực; hồ sơ và danh mục AI bổ sung tải nền riêng (timeout 8 giây), không chặn chat. Kết quả nền chỉ áp dụng nếu đúng phiên đăng nhập hiện tại. Tự đăng nhập bắt đầu sớm sau khi cửa sổ dựng xong. Quyền và xác thực server vẫn được giữ.

Yêu cầu một đường tròn có đủ thông số, ví dụ **Vẽ trong AutoCAD đường tròn tâm (0,0), bán kính 50 mm**, được phân tích trực tiếp nếu chỉ có một AutoCAD được phép. Luồng này tạo DXF và báo kết quả công cụ, không gọi model thêm để lập kế hoạch hoặc viết lại kết quả. Không đoán tâm, kích thước hoặc đơn vị khi dùng luồng nhanh; yêu cầu phức tạp hoặc ứng dụng chưa xác định tiếp tục qua AI. Khi chờ API lập kế hoạch, trạng thái hiện số giây chờ dịch vụ.


### Tạo bản vẽ 3D

Công cụ `cad3d_create_open` dùng cho cả AI trên máy và AI trực tuyến. Hỗ trợ khối hộp, khối trụ, mặt bích có lỗ tâm và 1–32 lỗ bu-lông chia đều xuyên chiều cao. Tạo DXF R2010 dạng MESH kín, kiểm tra cạnh kín trước khi lưu; đường tròn xấp xỉ 64 cạnh. Không phải ACIS solid, chưa hỗ trợ bo cạnh, không sửa DWG đang mở. Chỉ mở bằng acad.exe, chưa hỗ trợ AutoCAD LT. Kết quả gửi lệnh mở không đồng nghĩa đã xác minh cửa sổ AutoCAD.

Ví dụ: **Tạo mặt bích 3D trong AutoCAD, đường kính ngoài 240 mm, lỗ tâm 80 mm, dày 20 mm; 8 lỗ xuyên đường kính 18 mm trên vòng bu-lông đường kính 180 mm; tâm đáy (0,0,0), lỗ đầu ở hướng +X.** AI hỏi kích thước/đơn vị thiếu; không đoán. Quyền tự thực hiện đã lưu áp dụng công cụ này, vẫn có đếm ngược và nút dừng. Thư viện mapbox-earcut được cài nền theo quyền cài gói hiện có.

Khi đăng nhập, chuyển lịch sử khách sang tài khoản chạy trong worker, chỉ cập nhật hội thoại khách bằng SQLite JSON, không giải mã toàn bộ lịch sử trong giao diện. Trạng thái tài khoản hiển thị số giây; tooltip tách thời gian chờ server và xử lý trên máy. Nhật ký `login_timing` chỉ chứa hai số thời gian, không ghi mật khẩu/token. Thời gian này đo xác thực và chuẩn bị dữ liệu, không đo toàn bộ quá trình khởi động Windows/AutoCAD.


Lịch sử SQLite có chỉ mục theo chủ tài khoản và thời gian cập nhật. Đăng nhập/chuyển hội thoại khách và danh sách Gần đây dùng chỉ mục này, tránh quét/đọc nội dung của toàn bộ tài khoản. Lần đầu mở database cũ tạo chỉ mục; các lần sau dùng lại, không thay nội dung hội thoại.


### Khi khởi động/đăng nhập vẫn mất nhiều giây

UI không nạp Ollama để cài bộ lọc tiếng Việt lúc khởi động; bộ lọc được cài khi dùng client local hoặc Agent. Tự dò model local chỉ chạy khi chọn AI trên máy và sau tác vụ đăng nhập, không cạnh tranh nạp thư viện với AI trực tuyến.

Menu tài khoản/dấu ba chấm → **Sao chép thời gian khởi động/đăng nhập** trả báo cáo `startup-login-3`. Báo cáo chỉ chứa tên giai đoạn và số giây: nạp Qt, import desktop, cấu hình, SQLite, trạng thái module, dựng/hiện cửa sổ; khôi phục/lưu DPAPI, chờ header HTTPS, đọc response, tùy chọn model, chuyển chat khách, render hoàn tất worker và áp dụng giao diện. `startup.total` đo từ mã Python app.py, không gồm thời gian Windows nạp python.exe trước đó. `login.network_wait_headers` gồm DNS/proxy/TLS và chờ server, không được xem riêng là thời gian server. Báo cáo giữ trong RAM, tối đa 64 dòng, không ghi mật khẩu/token/nội dung chat và không đọc/ghi thêm file trên Google Drive. Chạy app.py để có đủ số đo khởi động, rồi dán báo cáo để xác định bước chậm; không cần Deploy lại server cho thay đổi này.

Đọc và giải mã đăng nhập đã ghi nhớ (DPAPI) cũng chạy nền, không chặn event loop; kết quả đọc muộn không thay tài khoản đã đăng nhập. Số đo `startup.crash_log` tách việc mở nhật ký trên Drive khỏi nạp Qt.
