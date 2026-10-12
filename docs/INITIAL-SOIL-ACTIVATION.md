# Bật đất ở InitialPhase, tránh quét lặp

InitialPhase không có PreviousPhase. inspect_stage/snapshot nay trả
parent_phase=null và parent_active=null, không truy cập Name của None.

verify_stage cho phép nhánh khởi tạo có giới hạn: kind=soil, after=true,
parent_phase=null và parent_active=null. Vẫn kiểm tra đúng đối tượng, vùng,
Active trước khi ghi và readback sau ghi. Không dùng nhánh này để tắt đất,
đào hoặc bật kết cấu/tải.

Khi người dùng đã yêu cầu bật toàn bộ đất ban đầu, dùng wrapper nội bộ
`initialize_soils` trong `plaxis_commands`. Đây không phải phương thức của g.
args là một JSON chứa:

- source: manual/mục hoặc yêu cầu khởi tạo rõ ràng.
- region: giới hạn x/y (và z khi là miền 3D), hữu hạn, đúng miền đất đã đọc.
- objects: toàn bộ tên khối g.Soils hiện tại → Active boolean thực tế.

Wrapper kiểm tra tập tên/identity, giới hạn và trạng thái hiện tại trước
khi ghi. Chỉ set True cho khối đang False, tại g.InitialPhase. Đất đã True
không được ghi lại. Sau đó đọc nhóm một lần để xác nhận; không đọc cả nhóm
trong vòng xác minh từng khối. Sai inventory/trạng thái, đổi phase/project,
đọc None, lệnh thất bại hoặc dừng giữa chừng phải dừng; không tự chạy lại
cả nhóm có thể đã thực hiện một phần.

Sau một nhóm initialize_soils thành công, kết quả đã có readback và phạm vi
chứng minh riêng. Wrapper không quét lại trạng thái tất cả phase/neo/tải để
tạo model_state. model_verified vẫn False nếu chưa verify_model đầy đủ.
Không dùng xác minh nhóm này làm bằng chứng toàn bài đúng manual/hội tụ.

AI được hướng dẫn dùng nhóm này sau khi đã có inventory; không đọc lại
inspect_stage/tabulate từng khối khi dữ liệu không có mâu thuẫn.

Kiểm tra nhóm mô phỏng hai khối: bốn lượt đọc Active (mỗi khối trước/sau),
chỉ một lệnh ghi cho khối False; phase thi công không bị ghi trực tiếp.
Bộ kiểm tra toàn dự án: 1.063 kiểm tra đạt. Chưa thử trực tiếp trên Windows.
