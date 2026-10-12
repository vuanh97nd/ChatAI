# Ghép bộ tính toán cũ vào bản hiện tại

Nguồn: `c20a72f`, ngày 11/10/2026 lúc 02:27:09 giờ Việt Nam.

Bộ sinh script và kiểm tra đầu vào được lấy từ phần hàm độc lập của
`assistant/plaxis_app.py` ở commit trên và đặt trong
`assistant/plaxis_calculation.py`. Adapter file/runtime hiện tại nhập các
hàm này qua cùng tên để giữ tương thích với giao diện và Remote API.
Không cần Git trên máy người dùng để chạy engine.

Đối chiếu AST: 18/19 hàm giống nguồn cũ. Hàm foundation_settlement giữ
bản sửa mới: đặt rõ Plane strain cho móng băng và mô tả đúng loại móng.
Không khôi phục nhãn axisymmetric sai của script móng băng cũ.

Giữ các sửa mới ở lớp điều khiển: kết nối đúng 2D/3D, đọc Active theo phase,
Parent.BoundingBox, tọa độ waterlevel, kiểm chứng vùng đào và trạng thái
tính. Giữ bộ nhớ, đồng bộ, token context và giao diện của bản hiện tại.
Không khôi phục việc tự new() xóa dự án đang mở hoặc coi phase chưa tính
là tính thành công.

Engine này sinh các script mẫu cho slope_stability, foundation_settlement,
retaining_wall, excavation_pit và embankment_stability theo phạm vi có sẵn.
Bài manual dùng Hoek-Brown/discontinuity không trở thành mẫu tự động mới;
vẫn thực hiện qua wrapper tổng quát và dữ liệu manual của đúng bài.

Đã chạy 180 kiểm tra liên quan: script, runtime giả lập, trạng thái phase,
automation và bộ nhớ. Chưa chạy tính trực tiếp trên PLAXIS Windows.
