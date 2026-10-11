# Chat AI: PLAXIS tools và API bất đồng bộ

## Các module đã tích hợp

- `assistant/plaxis_agent/schemas.py`: Pydantic strict, cấm trường thừa, NaN/Infinity và boolean thay số. Schema function calling được tạo từ model.
- `tools.py`: wrapper inspect, tạo vật liệu Mohr-Coulomb, thêm lớp 2D, verify/calculate. Không nhận code Python hoặc tên lệnh API từ LLM. Vật liệu dùng m/kN/kPa; kiểm tra đơn vị dự án trước khi ghi.
- `agent.py`: LangGraph reason → tools → reason, gọi `ChatOllama.ainvoke`, giới hạn lượt và timeout LLM. Không tự thử lại thao tác ghi lỗi.
- `runtime.py`: executor một worker; lệnh native không chặn event loop FastAPI.
- `jobs.py`: hàng đợi có giới hạn, chạy tuần tự cả công việc; trạng thái/events/kết quả và dừng trước bước kế tiếp.
- `router.py`, `api.py`: FastAPI 202 + polling; vòng đời đóng worker và logging xoay vòng.
- `utils.py`: khóa RLock dùng chung với `PlaxisRemoteApp.commit` của desktop trong cùng tiến trình.

Các tools `plaxis_safe_*` đã đăng ký vào Chat AI PC, đường online và Capabilities; tuân thủ cài đặt phương thức `application_api`. Qt tiếp tục dùng agent hiện có, còn dịch vụ API mới dùng LangGraph. Công cụ `plaxis_commands` cũ vẫn tồn tại cho tính năng nâng cao; agent API mới không được cấp công cụ đó.

## Chạy trên Windows có PLAXIS

```powershell
python -m pip install -r requirements-agent-api.txt
python -m pip install "plxscripting>=1,<2" "setuptools>=70,<81"
$env:CHATAI_AGENT_MODEL = "qwen2.5:7b"
python -m uvicorn assistant.plaxis_agent.api:app --host 127.0.0.1 --port 8765 --workers 1
```

Ollama phải chạy, đã tải model hỗ trợ native tool calling. Model DeepSeek-R1 không hỗ trợ tools ở một số bản phân phối; nếu Ollama báo không hỗ trợ thì chọn model có tool calling, không phân tích văn bản thành mã thực thi.

Mở PLAXIS Input, bật Expert → Configure remote scripting server → Start. API không tự mở/xóa dự án. Dịch vụ phải nằm trên máy Windows có PLAXIS; cloud không điều khiển localhost Windows của người dùng.

## Gửi công việc và đọc trạng thái

```powershell
$body = @{prompt="Đọc trạng thái PLAXIS hiện tại, chưa thay đổi dữ liệu";version="2d";max_steps=6} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/plaxis/jobs" -ContentType "application/json" -Body $body
Invoke-RestMethod "http://127.0.0.1:8765/plaxis/jobs/$($job.id)"
Invoke-RestMethod -Method Post "http://127.0.0.1:8765/plaxis/jobs/$($job.id)/stop"
```

OpenAPI: `/docs`. `/health` chỉ kiểm tra service, không xác nhận PLAXIS kết nối hoặc solver thành công. HTTP 202 nghĩa là đã nhận việc. `finished` chỉ là agent đã kết thúc; `model_completion_verified` hiện luôn false vì chưa có verifier trọn bài và đọc Output trong agent mới.

Có thể đặt `CHATAI_AGENT_API_TOKEN` rồi gửi header `Authorization: Bearer ...`. Mặc định chỉ bind loopback; không đưa API điều khiển máy lên Internet trực tiếp. Log tại `%LOCALAPPDATA%\ChatAI\logs\plaxis-agent.log`, tối đa 4 file × 2 MB. Log ghi tên tool, step, job ID và lỗi, không ghi prompt/token.

Đặt `CHATAI_AGENT_LOG_DIR` nếu cần chọn thư mục log khác có quyền ghi.

## Phạm vi và giới hạn

Wrapper thêm lớp cần đúng một borehole đã có. Chưa tạo contour/borehole, gán vật liệu, dựng kết cấu, tải, phase, HS hoặc trích xuất Output. Đây là nền tảng tích hợp có thể kiểm thử, chưa phải bộ tự chạy mọi bài manual. Không dùng kết quả `ok` của một tool để báo hoàn tất bài.

Stop không thể hủy solver đang chạy: chờ lời gọi native hiện tại kết thúc và dừng trước bước sau. Job lưu trong RAM, không tự phát lại sau restart; 32 job tối đa, job kết thúc cũ sẽ bị loại khi đầy. Dùng một worker Uvicorn và chỉ một ứng dụng điều khiển dự án; khóa Python không khóa giữa tiến trình API và một EXE desktop khác.

Test API cần dependencies trong requirements-agent-api.txt. Kiểm tra native Windows và các phiên bản PLAXIS vẫn phải thực hiện trên máy có phần mềm thật; mock không chứng minh đúng mô hình địa kỹ thuật.
