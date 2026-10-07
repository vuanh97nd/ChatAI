# Chat AI 2.6.5 — bộ cài Windows có runtime

## Build

Máy BUILD cần .NET Framework 4.x có csc.exe (hoặc Developer Pack), Windows x64, Python 3.12 bản đầy đủ từ python.org (có Python Launcher), Inno Setup 6.3+ và Internet. Người dùng cài EXE không cần cài Python hoặc thư viện nền.

1. Đóng Chat AI. Đợi Drive đồng bộ đầy đủ mã nguồn và logo_chat_ai.png.
2. Mở Build-Setup.bat. Runtime Python được sao chép từ Python của máy build, bỏ site-packages của người build rồi cài các thư viện từ requirements-bundled.txt vào runtime riêng.
3. Script kiểm tra import, kiểm tra sau khi đổi đường dẫn runtime, tạo icon robot nhiều kích thước và ảnh wizard, sau đó biên dịch Inno Setup.
4. Kết quả: `dist/Chat-AI-Setup-2.6.5.exe` là bộ cài một file, có Python runtime đóng gói bên trong. Nếu thất bại: build-logs/runtime.log hoặc build-logs/setup.log.
5. Cài thử trên Windows sạch không có Python, không có Ollama; mở shortcut, gửi câu Cloudflare và kiểm tra Office/web trước khi phát hành.

Không đóng gói .venv của người build, lịch sử SQLite, mật khẩu, config đang dùng của người khác, tài liệu cá nhân hoặc AI đã tải. Trước phát hành cần kiểm tra config.json là cấu hình mặc định không có đường dẫn cá nhân. Giữ các license/notice trong runtime và trong package; Python được sao chép kèm license của bộ cài Python.

## Mở ứng dụng

Shortcut chạy ChatAI.exe (C# GUI launcher, có icon robot), gọi runtime/python/pythonw.exe. run.bat chuyển sang ChatAI.exe; nếu chạy từ source chưa build thì dùng Launch-ChatAI.vbs. Chạy shortcut/ChatAI.exe không tạo console; mở BAT trực tiếp có thể thoáng hiện cửa sổ lệnh của Windows. desktop_launcher.py ghi stdout/stderr vào data/startup.log rồi mở app.py với splash Qt. Không gọi pip, không hỏi cài Python, không xuất hiện CMD trong ứng dụng đã cài. Dùng .venv/pythonw.exe làm phương án chạy từ mã nguồn nếu chưa build runtime. Nếu runtime hỏng/thiếu, báo lỗi thay vì tự tắt hoặc tải lại thư viện mỗi lần mở.

Bản cài chứa Python, Qt, Ollama SDK, pypdf và thư viện xử lý ảnh/video cơ bản Pillow, imageio, imageio-ffmpeg, OpenCV. Inno Setup đóng gói các thư viện này cùng runtime Python; chúng không cần tải riêng khi mở ứng dụng. Python sandbox cần Docker Desktop và image được tải sau khi người dùng bật module Python; image có thêm pandas/openpyxl, DOCX/PPTX và PDF. PyTorch CUDA cùng model sinh ảnh AI vẫn là mô-đun tải riêng, không nằm trong bộ cài. Dung lượng setup phải đo sau build trên Windows.

## Ollama tự động

Sau khi xác nhận tải AI local hoặc RAG, ứng dụng kiểm tra Ollama. Nếu thiếu, tải https://ollama.com/download/OllamaSetup.exe, hiển thị MB/tốc độ, xác minh chữ ký Ollama Inc., cài im lặng, khởi động dịch vụ loopback và chỉ tiếp tục tải model khi dịch vụ đã trả phiên bản. Ollama hiện có không tự bị nâng cấp/cài lại. Web, Office và Cloudflare không yêu cầu Ollama.

Tiến độ/lỗi hiển thị trong trang tải; nhật ký ở %LOCALAPPDATA%/ChatAI/install-logs. Phần mềm không tự tắt Ollama đang được ứng dụng khác sử dụng. Giữ cấu hình GGML_CUDA_PDL đã đặt trước đó khi khởi động dịch vụ.

## Kiểm thử trước phát hành

- Cài trên Windows x64 sạch, kiểm tra mở không CMD và không hộp cài Python/thư viện.
- EXE, shortcut, thanh tác vụ và wizard có logo robot.
- Thiếu Ollama: tải Qwen 3B, kiểm tra cài dưới nền rồi tải AI; thử mất Internet và lỗi chữ ký.
- Ollama đã cài nhưng đang tắt: khởi động lại, không tải bộ cài mới.
- Cập nhật cùng AppId giữ config, hội thoại và tài liệu; gỡ cài đặt không xóa dữ liệu tạo thêm.
- Kiểm tra tạo ảnh/RAG optional và nhật ký khi ứng dụng lỗi.

Code đã kiểm thử tự động ở mức Python; EXE chỉ được xác nhận sau khi build và chạy thử trên Windows. Bộ cài chưa ký số; icon không thay thế chữ ký số của nhà phát hành.

## Tạm dừng / hủy tải AI

Trang Tải mô hình có Tạm dừng tải, Tiếp tục tải và Hủy tải. Ngắt yêu cầu pull và đóng stream ở điểm an toàn khi có phản hồi từ Ollama; trong lúc mạng chờ, việc dừng có thể không tức thời. Tiếp tục tạo yêu cầu mới cùng tên AI để Ollama tận dụng cache nếu còn; không đảm bảo tiếp tục chính xác từng byte. Hủy không xóa model đã cài hoặc tự xóa blob/cache Ollama. Các nút này áp dụng cho tác vụ tải AI trực tiếp, không ngắt bộ cài thư viện đang thực thi.

## Gỡ AI

Chọn AI trong trang Tải mô hình rồi bấm Gỡ AI đã chọn. Cần xác nhận, và phải đợi các tác vụ tải/cài đang chạy kết thúc. Gỡ qua Ollama API, kiểm tra model không còn trong danh sách rồi cập nhật giao diện. Không xóa chat, tài liệu hay lựa chọn AI đã lưu; nếu lựa chọn trỏ đến AI đã gỡ, cần chọn AI khác hoặc tải lại. Dung lượng giải phóng phụ thuộc các blob có được AI khác dùng chung hay không.


## Bản sửa code và lỗi six/Qt

- Máy build dùng Python **3.12.10 trở lên trong nhánh 3.12**, 64-bit. Runtime đóng gói gồm `six` và xử lý tương thích trước khi nạp Qt. Nếu vẫn thấy `_SixMetaPathImporter ... _path`, gửi `data/crash.log` và `data/startup.log` (không gửi mật khẩu).
- Trong khối code có **Sao chép**, **Lưu file**, **So sánh với file gốc**. Code không tự chạy. Nút sao chép giữ thụt dòng và xuống dòng, dùng được cả lịch sử cũ.
- Đính kèm file mã nguồn UTF-8, yêu cầu AI trả toàn bộ file. So sánh có lựa chọn **Lưu bản mới** / **Ghi đè file gốc**. Ghi chỉ trong thư mục whitelist đã cấu hình; luôn xác nhận, backup file có sẵn và ghi audit. Không cần thư viện xử lý code mới.
- File đã lưu xuất hiện tên và nút **Mở thư mục** trong khối code của hội thoại. Bản code trong lịch sử vẫn có thể lưu lại nếu file trên đĩa bị mất.
- Nếu nguồn bị rút gọn do ngân sách ngữ cảnh hoặc quá lớn, chỉ lưu bản mới; không cho ghi đè qua thao tác so sánh. File nhị phân/Office dùng công cụ Office riêng, không được ghi lại bằng code văn bản.
- Với bộ cài EXE cũ, chạy lại **Build-Setup.bat** trên máy build rồi cài bản mới để nhận thay đổi này. Sửa mã nguồn không tự thay đổi EXE đã phát hành.


## AI lập trình lớn (tải riêng theo lựa chọn)

| AI trong ứng dụng | Tag Ollama | Dung lượng tải xấp xỉ | Gọi công cụ trực tiếp |
| --- | --- | --- | --- |
| DeepSeek-Coder-V2 Lite 16B | `deepseek-coder-v2:16b` | 8.9 GB | Không |
| Qwen2.5-Coder 32B | `qwen2.5-coder:32b` | 20 GB | Có |
| Codestral 22B | `codestral:22b` | 13 GB | Không |
| DeepSeek-Coder 33B | `deepseek-coder:33b` | 19 GB | Không |

Đối chiếu thư viện Ollama ngày 06/10/2026; kích thước tag có thể thay đổi. DeepSeek-Coder-V2 được chọn bản Lite 16B, không tải bản 236B. Nút tải luôn hỏi trước, hiển thị lưu ý cấu hình và dung lượng. Các AI mới dùng chung tải nền, tạm dừng, tiếp tục, hủy, gỡ và lưu lựa chọn theo tài khoản. Không đổi AI mặc định, không tự tải hoặc đưa trọng số vào bộ setup. RAM 16 GB / VRAM 8 GB không bảo đảm chạy tốt các AI này; giữ các bản 3B/7B nếu cần tốc độ.

Nguồn: https://ollama.com/library/deepseek-coder-v2:16b ; https://ollama.com/library/qwen2.5-coder:32b ; https://ollama.com/library/codestral:22b ; https://ollama.com/library/deepseek-coder:33b .


## Phối hợp AI tuần tự trong cùng cuộc hội thoại

- Ví dụ: **“Tạo ảnh logo robot và viết code HTML dùng ảnh đó.”** Chọn AI local, bật/tải công cụ ảnh/video. Chọn SD-Turbo nhanh hoặc SDXL-Turbo chất lượng cao trong mục Tải mô hình; ứng dụng yêu cầu tạo ảnh theo model đã chọn, hiện xác nhận rồi bàn giao file thật cho AI lập trình. Không gọi model ảnh là mô hình ngôn ngữ. Bộ setup vẫn không kèm trọng số.
- Dữ liệu bàn giao gồm tên file, đường dẫn trong whitelist, dung lượng, SHA-256 và kích thước ảnh đã đọc từ file. Không chuyển ảnh thành một mô tả tưởng tượng. Nếu file bị sửa/mất, không dùng manifest cũ như bằng chứng.
- Nếu chọn sẵn AI chuyên code (Qwen Coder, DeepSeek Coder, Codestral), tiếp tục dùng AI đó. Nếu chọn AI chat, dùng `code_model` đã lưu khi được Ollama báo đã cài. Chưa có AI code thì dùng AI hiện tại và thông báo; không tải thêm tự động.
- Muốn dùng ảnh đã tạo: **“Viết code Python gửi ảnh vừa tạo.”** Ứng dụng bàn giao tài nguyên từ cùng cuộc hội thoại. Chỉ lấy kết quả tool thật, không lấy đường dẫn do AI tự viết trong câu trả lời.
- Muốn dựng giao diện từ ảnh chụp: gửi ảnh với Gemma3 4B đã tải, hỏi **“Viết code HTML theo ảnh này.”** AI vision mô tả bố cục, rồi chuyển cho AI code. Mô tả vision được đánh dấu có thể sai, không coi là văn bản OCR đã xác minh. AI code không nhận ảnh qua model văn bản.
- Từng bước chạy nối tiếp, giải phóng AI điều phối trước khi nạp AI code; không chạy các LLM và diffusion đồng thời. Các bước và trạng thái có trong SQLite/audit, tiếp tục qua nút duyệt hiện có.
- Tạo ảnh/video, ghi file và chạy công cụ vẫn tuân thủ quyền hiện có. Từ chối tạo ảnh sẽ được báo đúng cho AI code, có thể dùng placeholder được ghi nhãn. Không tự tìm mạng khi nút **Tìm kiếm mạng** tắt. Cloudflare hiện chưa có phối hợp công cụ local; chọn AI local để dùng luồng này.
- Đây là điều phối AI/công cụ, không phải huấn luyện lại hoặc các AI tự học lẫn nhau. Giữ nguyên giao diện và các nút hiện có.


## Quản lý người dùng / hỗ trợ (cần Deploy Worker mới)

- Đăng nhập quản trị viên được server xác nhận (`role=system`). Sidebar và menu tài khoản có **Quản lý người dùng**; Hỗ trợ mở thẳng **Yêu cầu người dùng**, kèm người gửi, thời gian, lọc chưa đọc/chưa xử lý và trả lời/đổi trạng thái. Không cấp quyền bằng họ tên hiển thị.
- Danh sách người dùng có tìm kiếm, lọc hoạt động/bị khóa/đã xóa mềm, phân trang 100 dòng. Chi tiết gồm liên hệ, thời hạn, ngày cập nhật hồ sơ và nhật ký thao tác quản trị; không trả mật khẩu, salt, hash, khóa hoặc token.
- Khóa, mở khóa, thu hồi đăng nhập, chỉnh sửa/gia hạn và xóa mềm đều cần xác nhận. Xóa mềm nhập lại tên tài khoản, giữ dữ liệu, cho khôi phục trong 30 ngày. Sau 30 ngày không còn nút khôi phục hợp lệ; bản này không tự xóa vĩnh viễn dữ liệu hoặc file local. Không xóa tài khoản hệ thống.
- Worker tự bổ sung các cột `account_status`, `deleted_at`, `created_at`, `session_epoch` vào `users`, tạo bảng `account_tokens`, `admin_audit`. Ngày tạo của tài khoản cũ chưa ghi nhận không được suy đoán. Không cần chạy SQL thủ công; migration chạy lần đầu sau Deploy. Nên dùng bản sao lưu D1 hiện có trước Deploy.
- Người dùng thường nhận token phiên 30 ngày sau đăng nhập, lưu bằng DPAPI Windows. Khóa/xóa/thu hồi tăng phiên bản và hủy token. App gửi presence mỗi 30 giây; online là heartbeat gần nhất dưới 90 giây. Khi API báo phiên bị thu hồi, ứng dụng chuyển về khách; không xóa lịch sử local. Ứng dụng cũ lưu mật khẩu cần đăng nhập lại sau thu hồi và nên cập nhật bộ cài.
- File `work.js` và `server/worker.js` đồng nhất. Upload/Deploy `work.js` lên Worker đang dùng; giữ binding D1 **DB**, secret **ADMIN_KEY** và các binding/secret AI/bộ nhớ đang có. Chỉ cập nhật file trong Google Drive chưa làm server đang chạy thay đổi.
- Theo yêu cầu của người dùng, thay đổi này chưa chạy lại bộ kiểm thử hay kiểm tra Windows.


## Tìm kiếm mạng trực tiếp

Bing dùng thư viện chuẩn Python, không cài module mạng. Đã bỏ hàng Bật/Tải/Tắt mạng và bỏ điều kiện tải module trước khi gửi. Tùy chọn `web=0` lưu từ bản cũ không còn chặn tra cứu. Bấm Tìm kiếm mạng khi đã nhập câu hỏi sẽ gửi tra cứu ngay; chưa nhập thì đưa con trỏ vào khung nhập. Bấm lần nữa tắt tìm mạng. Chỉ khi nút bật mới tìm/đọc web; vẫn cần Internet và AI local đã tải (hoặc AI server được phép dùng). Theo yêu cầu, không chạy lại kiểm thử cho thay đổi này.
