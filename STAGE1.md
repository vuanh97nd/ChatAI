# Chat AI — Giai đoạn 1

Đã tích hợp vào vòng lặp Agent hiện tại; không cần thay desktop_ui.py hoặc thêm nút.

File mới:
- assistant/prompts.py: system prompt tiếng Việt 570 từ; kèm quy tắc công cụ, tổng prompt 693 từ ở chế độ công cụ.
- assistant/routing.py: phân loại 7 nhóm bằng một request JSON schema tới qwen2.5:7b; có dự phòng khi request lỗi hoặc JSON không hợp lệ. Lời chào ngắn đi thẳng tới trả lời.
- tests/test_routing.py: kiểm thử phân loại, lỗi, nhiệt độ, tích hợp và lưu trạng thái.
- STAGE1.md: hướng dẫn này.

File sửa:
- assistant/agent.py: start() đặt routing=None cho lượt mới; run() phân loại một lần trước vòng gọi công cụ, lưu routing cùng lịch sử SQLite; mọi vòng trả lời trong lượt dùng nhiệt độ đã chọn. Tiếp tục sau xác nhận không phân loại lại.
- tests/test_app.py: backend giả lập xử lý request phân loại tách biệt với streaming.

Nhiệt độ:
| Loại | Nhiệt độ |
|---|---:|
| Trò chuyện | 0.5 |
| Kiến thức, tính toán, code, thông tin mới, tài liệu riêng | 0.2 |
| Viết/dịch thông thường | 0.3 |
| Viết sáng tạo | 0.75 |

Giữ qwen2.5:7b cho phân loại. Không đổi model đang chọn trong giao diện; khi dùng qwen2.5:7b để chat, cả hai lượt dùng cùng model. Model chọn sẵn và cấu hình khác được giữ nguyên. Đầu ra classifier chỉ gồm nhãn/boolean; không đưa suy luận nội bộ lên giao diện. Classifier không nhận payload ảnh hoặc toàn văn tài liệu.

Các cờ complex/high_accuracy chỉ đánh dấu review_recommended trong dữ liệu lượt chat. Giai đoạn 1 chưa thực hiện thêm lượt rà soát; chat thường không có lượt rà soát. Không tự bật tìm mạng dựa vào nhãn: tìm kiếm hiện tại hoạt động như trước, cải tiến ở Giai đoạn 2.

Chạy Windows:
1. Đóng Chat AI đang mở.
2. Đợi Google Drive đồng bộ các file mới/sửa vào G:\My Drive\Dev\Chat-AI.
3. Mở Ollama và bảo đảm qwen2.5:7b đã cài. Nếu chưa: `ollama pull qwen2.5:7b`.
4. Chạy run.bat như trước. Không có thư viện mới cần cài cho giai đoạn này.

Kiểm thử tự động trong CMD từ thư mục dự án:
```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
Nếu môi trường của bạn dùng tên khác, thay .venv bằng môi trường run.bat sử dụng.

Thử thực tế:
- "Xin chào!": trả lời nhanh, không gọi model phân loại.
- "Giải thích định luật Newton": kiến thức, nhiệt độ 0.2.
- "Sáng tác một bài thơ về Hà Nội": viết sáng tạo, nhiệt độ 0.75.
- "Dịch đoạn này sang tiếng Việt: Good morning": viết/dịch, nhiệt độ 0.3.
- "Viết code Python đọc CSV": code, nhiệt độ 0.2.
- Gửi kèm tài liệu: ưu tiên personal_documents, nhiệt độ 0.2.

Nhãn là kết quả dự đoán, không bảo đảm tuyệt đối. Quy tắc dự phòng cũng có thể phân loại sai; nó giúp lượt chat tiếp tục khi classifier thất bại. Câu không thuộc lời chào thêm một request ngắn nên có chi phí độ trễ. Quy trình này cải thiện cách điều phối, không biến 7B thành model biết mọi thứ.

Kiểm thử bằng backend giả lập xác nhận giao thức, chọn nhiệt độ, streaming/lưu lịch sử và xác nhận công cụ. Chưa kiểm thử Ollama/GPU hoặc mở giao diện thực trên Windows trong môi trường này.
