# Kiểm tra công cụ Windows — 10/10/2026

## Tiến trình quan sát được

ChatAI PID 39516 khởi động 17:29:51 (Asia/Saigon):

- Interpreter: `G:\My Drive\Dev\Chat-AI\Chat AI 2.6.6\runtime\python\pythonw.exe`
- Script: `desktop_launcher.py` trong cùng thư mục.
- Working directory: `G:\My Drive\Dev\Chat-AI\Chat AI 2.6.6`.
- PLAXIS đang chạy từ `C:\Program Files\Seequent\PLAXIS 2D 2024\Plaxis2DXInput.exe`; nhiều tiến trình xuất hiện. Chưa xác định cửa sổ nào chứa dự án bằng computer-use, không suy ra số dự án hoặc tunnel từ số tiến trình.

Tiến trình xuất hiện sau lần kiểm tra đầu không thấy ứng dụng. PID và trạng thái này là ảnh chụp tại thời điểm kiểm tra, không phải định danh cố định.

Metadata hội thoại gần nhất: model `DeepSeek Flash`, `online_automation=true`, `running=false`, không có bước chờ duyệt. Không đọc/in khóa tài khoản. Các quyền Windows và quyền tự thực hiện đang bật.

## Schema và bộ lọc

Bắt lời gọi `client.chat` của `OnlineAutomation.run` bằng client giả lập, với ngữ cảnh PLAXIS và `plaxis_general_mode=true`. System prompt thực tế chứa các schema:

`browser_run`, `browser_search`, `plaxis_commands`, `windows_action`, `windows_attach`, `windows_capture`, `windows_input`, `windows_inspect`, `windows_list_apps`, `windows_list_windows`, `windows_open`.

Không thiếu bốn công cụ visual. Online dùng JSON planner: schema nằm trong system prompt sau “Công cụ:”, không dùng tham số native `tools` của provider. Đây là kiểm tra payload dựng bởi mã nguồn/runtime đang có, không phải bắt request của tiến trình ChatAI đang chạy hoặc gọi provider thật.

- Đăng ký: `assistant/tools.py`, nhóm `windows`, tất cả thuộc `WRITES`.
- Bộ lọc PLAXIS: `_PLAXIS_TOOLSET` hợp với `VISUAL_TOOLS` trong `assistant/online_automation.py`.
- Thực thi online: `OnlineAutomation.component` → `WindowsApps.prepare/commit` → `VisualWindows` → `VisualBackend`.
- Thực thi local: `Capabilities` chuyển tên bắt đầu `windows_` sang `WindowsApps`.
- `windows_input` hỗ trợ click trái, `press_key`, `type_text`; `windows_capture` dùng PrintWindow. Sau input, chụp lại và đưa ảnh riêng vào message, không nhét Base64 vào JSON bị cắt.
- Luồng local cố ý loại `windows_input` khi model không đọc ảnh. Không bỏ chốt này để model văn bản đoán tọa độ. Hội thoại gần nhất là online nên không đi qua bộ lọc local này.

Commit `2356075` đã bổ sung điều khiển giao diện. Bản sửa vùng đào sau đó thêm `inspect_stage`/`verify_stage` vào `plaxis_commands`; riêng bản vùng đào không thêm chuột/phím/chụp màn hình. Chốt vùng đào hiện chỉ xác minh phạm vi hộp/chữ nhật do caller cung cấp; chưa xác thực manual hoặc biên tunnel cong và không áp dụng cho thao tác UI. Không khai vùng hộp thay biên cong để vượt kiểm tra.

## Kiểm thử

`tests/test_windows_visual_routes.py` kiểm tra schema sau bộ lọc ngay trong payload `client.chat`, và chạy xuyên planner → WindowsApps → backend giả lập → ảnh sau thao tác được đưa vào request tiếp theo. Không gọi provider, không click cửa sổ thật, không mở PLAXIS hay tạo dự án.

65 kiểm thử liên quan đã đạt khi chạy bằng `runtime/python/python.exe`, gồm schema/dispatch, visual, chốt vùng đào và Stop. Đây là kiểm thử giả lập.

## Bước chưa hoàn tất

Computer-use timeout ngay khi import `@oai/sky`: `js execution timed out; kernel reset, rerun your request`. Vẫn lỗi sau thử lại/reset. Chưa có screenshot/handle cửa sổ thật nên chưa kiểm thử trực tiếp hoặc cho AI tiếp tục bài. Chưa chủ động khởi động lại ChatAI trong lần kiểm tra này. Không tạo project/tunnel hoặc thay dữ liệu manual.
