# Chat AI Desktop 2.6.6

Ứng dụng Windows native bằng PySide6, chạy mô hình trên Ollama local. RAM16GB/RTX3070 8GB: Qwen2.5 7B mặc định, Qwen Coder7B cho code; có Qwen1.5B/3B, DeepSeek R1 1.5B/8B, Gemma3 4B đọc ảnh.

**Bản này bắt buộc đăng nhập server trước khi chat theo yêu cầu mới.** Suy luận vẫn chạy local; xác thực và bộ nhớ riêng dùng server Cloudflare. Cần server đã triển khai và Internet để xác thực. Chưa tự triển khai server hoặc tạo GitHub Release trong phiên này.

## Cài và chạy Windows

1. Cài Python3.12 64-bit (hoặc3.11); bật Python Launcher. Bản này chưa hỗ trợ Python3.14.
2. Cài Ollama, mở Ollama và chạy dịch vụ mặc định `http://127.0.0.1:11434`.
3. Đợi Google Drive đồng bộ đầy đủ thư mục Chat-AI; đóng bản cũ, chạy `run.bat`. Launcher tạo `.venv`, hỏi trước khi tải thư viện. Không cần Streamlit hoặc mở trình duyệt.
4. Triển khai `work.js` lên Cloudflare Worker với DB/ADMIN_KEY theo `server/README-server.md`. Muốn bộ nhớ cá nhân, thêm MEMORY_KV và MEMORY_ENCRYPTION_KEY.
5. Trong Chat AI → Cài đặt, nhập URL gốc HTTPS của Worker, ví dụ `https://your-worker.your-subdomain.workers.dev`. Đăng ký bằng Họ và tên, Tên đăng nhập, Mật khẩu; hoặc đăng nhập tài khoản có sẵn.
6. Ô “Ghi nhớ đăng nhập” mặc định được tích. Mật khẩu được che bằng ký tự • và lưu mã hóa DPAPI của Windows, không nằm dạng plaintext trong config/SQLite. Bỏ tích để không lưu. Đăng xuất xóa file đăng nhập đã lưu.
7. Module / Tải xuống: chọn model và xác nhận tải. AI không tự tải model hoặc thư viện nếu chưa được duyệt. Qwen3B phù hợp khi muốn trả lời nhanh hơn. DeepSeek R1 8B dùng chat/suy luận; công cụ native chọn Qwen.
8. Quay lại chat, gửi câu hỏi bằng Enter; Shift+Enter xuống dòng.

Nếu không chạy được, gửi `data/startup.log` và `data/install-base.log`. Không gửi file `login.dpapi` hoặc API secrets. Không chép `.venv` giữa máy hoặc thư mục khác; launcher dùng Python3.11/3.12 để tạo đúng môi trường.

## Giao diện và thao tác

- Logo robot; màn hình khởi động có chấm chạy và lời nhắn “Xin vui lòng đợi trong giây lát”. Backend/SQLite nạp ở luồng nền, không chặn event loop; số giây chờ là thời gian thực, không phải phần trăm giả.
- Thanh bên cố định240px; trang Cài đặt tối đa860px, không giãn toàn màn hình.
- Đã bỏ hộp chọn “Chat nhanh” trên đầu cửa sổ. Nút Tạo ảnh, Tạo video, Tìm kiếm mạng nằm trong khung nhập; công cụ Office/AI tự động bật từ Cài đặt.
- Ba chấm chạy ở giữa vùng trạng thái khi AI đang phản hồi; bấm để xuống phần mới nhất. Tự cuộn khi đang ở cuối; đọc tin cũ không bị kéo xuống liên tục.
- Ctrl+V dán ảnh clipboard hoặc file ảnh được copy, có xem trước và Bỏ ảnh. Mỗi lượt1 ảnh, nén JPEG cạnh tối đa1600px/1.5MB. Chọn thumbnail rồi Ctrl+C, hoặc bấm Copy ảnh, để sao chép. Chọn ảnh trong lịch sử chat rồi Ctrl+C; chọn văn bản thì Ctrl+C vẫn copy chữ.
- Ảnh được lưu trong lịch sử local và gửi tới Ollama. Model văn bản không nhận ảnh; app hỏi chuyển sang Gemma3 4B và hỏi tải nếu chưa có. Chỉ ảnh gần nhất được đưa vào context vision để giảm VRAM.
- Xóa cuộc trò chuyện có xác nhận và backupJSON; có toàn bộ lịch sử, log và nút quay lại trên các trang tiện ích.

## Tra web và Python tự động

Nút Tìm kiếm mạng bật/tắt tra DuckDuckGo, đọc nguồn bằng trafilatura rồi đưa dữ liệu vào model để suy luận/tổng hợp, kèm URL. Chỉ câu hỏi được gửi lên dịch vụ tìm kiếm; ảnh clipboard không gửi lên DuckDuckGo. Câu hỏi tra mạng tối đa500 ký tự. DeepSeek vẫn dùng được chế độ này vì tra cứu thực hiện trước khi suy luận, không cần native tool calling.

Cài đặt → “Dùng công cụ AI tự động trong chat” bật agent gọi tool (Qwen), cần tải/bật module Web và Python trước. Python cần Docker Desktop/Linux containers và image đã được duyệt tải. Theo quyền đã cấp, “AI tự viết/chạy Python tra cứu trong Docker” mặc định bật, có thể tắt.

- `python_run`: chạy Python trong Docker với pandas/openpyxl/pypdf/python-docx và Pillow/imageio/imageio-ffmpeg/OpenCV; lỗi được trả cho AI, tối đa3 lần chạy/sửa mỗi lượt. File ảnh/video trong `/output` được lưu vào `workspace/outputs` (tối đa10 file/50 MiB) sau khi người dùng duyệt chạy code.
- `python_search`: AI viết code dùng `web_search(query)` và `web_read(url)`, lọc/tính/tổng hợp kết quả, in ra nguồn. Bridge host thực hiện tối đa4 yêu cầu web/code; container không có truy cập mạng trực tiếp. Kết quả lấy được làm đầu vào cho lần chạy lại, lỗi trả về model để sửa.
- Container: 512MiB RAM,1CPU,30 giây mỗi lần, không GPU, mount chỉ đọc, file tạm bị xóa. Không chạy code sinh bởi AI trực tiếp trên Windows và không biến tool thành quyền ghi tùy ý ngoài whitelist.
- File/Excel/Office ghi, sửa, xóa, chạy shell vẫn có xác nhận/backup/audit. Auto-Python chỉ bỏ hộp duyệt cho Python cách ly theo quyền mới; không tự duyệt tất cả lệnh host hoặc thay cấu hình whitelist.

## Office, RAG và ảnh/video

Excel XLSX: liệt kê sheet, đọc ô/công thức, tóm tắt, sửa ô có backup. Word DOCX/PowerPoint PPTX: đọc/tạo, sửa text Word; mở bằng Microsoft Office/LibreOffice nếu máy đã cài. Không hỗ trợ macro, DOC/PPT cũ hoặc tự động COM Office.

File tools chỉ hoạt động trong whitelist. RAG dùng ChromaDB và nomic-embed-text; tài liệu/embedding ở máy. Tra web cần Internet; riêng câu hỏi tra cứu được gửi tới dịch vụ.

Thư viện cơ bản Pillow, imageio, imageio-ffmpeg và OpenCV được đóng gói trong runtime desktop và Python sandbox. Công cụ ảnh cơ bản dùng ngay: đổi kích thước ảnh; công cụ video ghép ảnh thành slideshow MP4 720p có chuyển động zoom/pan. Ảnh/video đầu ra nằm trong workspace/outputs sau khi duyệt thao tác. AI cũng có thể dùng các thư viện trong Python sandbox đã bật. Mô-đun ảnh AI cho chọn SD-Turbo FP16 (nhanh) hoặc SDXL-Turbo FP16 (chất lượng/bám prompt tốt hơn), tải model được chọn dưới nền; cả hai tạo PNG 512×512. SDXL-Turbo lớn hơn, cần dung lượng đĩa và có thể chậm hơn khi phải tiết kiệm VRAM. Hiện chưa có model video diffusion để tạo cảnh video AI chất lượng cao.

Tiến độ tải model ghi SQLite khoảng1 lần/giây khi layer/trạng thái không đổi, thay vì mỗi chunk. Có MB/s và ETA cho layer đang tải. Cache pip/Ollama/Hugging Face được giữ để tiếp tục tải dở. Tốc độ phụ thuộc mạng, server tải và ổ lưu trữ. Chưa đo tốc độ trên máy Windows của bạn.

## Tài khoản và bộ nhớ riêng

Cài đặt → Bộ nhớ cá nhân trên server: xem/thêm/sửa/xóa ghi nhớ sau đăng nhập. Mỗi tài khoản có bộ nhớ riêng; server tự dùng đúng tài khoản đã xác thực, không nhận owner tùy ý từ client. AI local nạp profile trước lượt chat; nếu dịch vụ bộ nhớ tạm lỗi, chỉ dùng cache RAM của cùng tài khoản. Đổi tài khoản/đăng xuất xóa cache RAM đó.

Nội dung bộ nhớ mã hóa AES-GCM trong Workers KV; D1 chỉ lưu owner/id/revision. D1 loại mục đã xóa trước khi lấy KV để không đưa dữ liệu KV cũ sau xóa vào prompt. Ghi mới cần người dùng xác nhận; không tự lưu toàn bộ chat thành ghi nhớ. KV không phải Chroma RAG. API cloud cũng dùng bộ nhớ theo tài khoản khi trả lời.

Không lưu profile cá nhân vào JSON state của hội thoại local. Lịch sử local cũ chưa có nhãn tài khoản được giữ để không mất dữ liệu; hội thoại mới gắn account_username, không tiếp tục AI/tool của tài khoản khác. Đây không phải cơ chế phân quyền hệ điều hành: người có quyền đọc thư mục dữ liệu local vẫn có thể đọc lịch sử local.

## Cài đặt và cập nhật

Cài đặt có model chat/code, context, token tối đa, độ sáng tạo, cỡ chữ, số vòng tool, whitelist, tài khoản, bộ nhớ và GitHub cập nhật. Lưu config cần xác nhận, backup config trước khi thay.

Updater dùng https://github.com/vuanh97nd/ChatAI/releases. Kiểm tra khi người dùng bấm, không gọi lúc khởi động. Hiển thị version/notes; tải dưới nền sau đồng ý vào `%LOCALAPPDATA%/ChatAI/updates`; kiểm kích thước và SHA256 nếu GitHub có digest. Không tự chạy EXE. Xem RELEASE.md và CHANGELOG.md cho phát hành sau.

## Bộ cài Inno Setup

Cài Inno Setup 6.3+ hoặc 7 từ https://jrsoftware.org/isdl.php. Mở `Chat-AI-Setup.iss` → Build → Compile hoặc chạy `Build-Setup.bat`. Bộ cài tạo tại `dist/Chat-AI-Setup-2.6.6.exe` và đóng gói Python runtime trong một file EXE.

Bộ cài mặc định vào `%LOCALAPPDATA%/Programs/Chat-AI`, có Start Menu và tùy chọn Desktop. Máy đích không cần cài Python riêng; cần cài Ollama và tải model để dùng AI local. Giữ config hiện có khi nâng cấp; gỡ cài giữ dữ liệu/workspace. Không tự chuyển lịch sử từ thư mục Google Drive sang thư mục cài mới.

## Điều khiển ứng dụng Windows

Có thể cho AI local mở EXE được phép và thao tác control UI Automation sau khi duyệt từng bước. Bật trong Cài đặt → Điều khiển ứng dụng. Cần thư viện tùy chọn; xem [hướng dẫn và phạm vi hỗ trợ](WINDOWS_AUTOMATION.md). Không bảo đảm mọi app hoặc chạy hoàn toàn trong nền.

## Android (APK thử nghiệm)

Bản Flutter trong [`mobile/`](mobile/README.md) dùng chung tài khoản, bộ nhớ cá nhân
và ví server; mặc định NVIDIA trực tuyến. GitHub Actions **Build Android APK**
kiểm thử và xuất APK cài thử khi cập nhật `mobile/`. Xem hướng dẫn tải/build/ký
APK và phạm vi chức năng trong tài liệu Android; bản này chưa chạy PLAXIS/GeoStudio.
