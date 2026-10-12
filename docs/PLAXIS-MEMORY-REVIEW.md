# Bộ nhớ PLAXIS: rà soát và sửa kết nối

Luồng Agent thường đã gọi CaseMemory.capture/context, nhưng luồng
OnlineAutomation dùng để điều khiển PLAXIS chưa có hai bước này.
Bản sửa nối lưu kết quả bài tính và truy hồi bài cũ vào luồng trực tuyến.
Chỉ lấy bộ nhớ liên quan (tối đa 2.000 ký tự), không gọi LLM/embedding thêm.

CaseMemory.capture trước đây chấp nhận mọi plaxis_commands có ok=true,
kể cả đọc inventory/tạo vật liệu không có kết quả tính. Nay chỉ tự lưu
khi có kết quả kỹ thuật có cấu trúc, không lưu uncertain/results_unavailable
như bài đã tính. Giữ các tên có đơn vị như max_settlement_mm; không tự đổi đơn vị.
Không xóa hay đổi lịch sử/bản ghi cũ của người dùng.

Lỗi ghi CaseMemory được ghi bằng loại lỗi trong audit, không biến một thao tác
PLAXIS đã thành công thành lỗi để chạy lại. Nếu không có kết quả kỹ thuật nhận
diện được, vẫn lưu tiến độ/lời gọi trong ProcedureMemory và lịch sử công cụ.

Bộ nhớ bài cũ là dữ liệu tham khảo, không chứng minh trạng thái dự án hiện tại.
Sau mở lại PLAXIS/mesh/đổi file phải xác nhận phiên, đối tượng và phase thực tế.
Không tự phát lại lệnh ghi, mang GUID/ref cũ sang phiên mới hoặc coi Active=None
là False. Bộ nhớ nằm trong database/cache; một bản ứng dụng cũ có thể chưa có
logic đọc/ghi mới, dù file dữ liệu vẫn còn.

Đã kiểm tra lưu kết quả từ OnlineAutomation, đọc lại trong prompt kế tiếp,
cách ly chủ tài khoản, bỏ qua lệnh đọc không có kết quả và trạng thái uncertain.
Chưa có log/model/file từ phiên máy Windows của người dùng để kết luận nguyên
nhân riêng của việc “hôm qua được, hôm nay không được”.
