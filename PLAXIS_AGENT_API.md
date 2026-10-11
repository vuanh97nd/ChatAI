
## Đọc tiến độ và tiếp tục mô hình đang dở (bộ điều khiển desktop)

Hai lệnh đọc-only mới qua `plaxis_commands`: `inspect_progress` và `plan_resume`.
Chúng đọc collection thật ở mỗi lần gọi, không dùng alias đất/phase lưu từ trước.
Không đổi chế độ hoặc tạo/xóa mô hình. Nếu collection không đọc được trong chế độ
hiện tại, báo `unreadable`; không coi đó là số đối tượng bằng 0.

Đọc danh sách hiện tại và trạng thái các phase trước:

```json
[{"command":"inspect_progress","args":[{}]}]
```

Sau khi đọc đúng manual, cung cấp các điều kiện cần đối chiếu. Ví dụ dưới đây chỉ
minh họa định dạng; thay toàn bộ số liệu và tên bằng dữ liệu của bài đang làm:

```json
[{"command":"plan_resume","args":[{
  "source":"Manual đang dùng, chương/mục/trang đã đọc",
  "checks":[
    {"ref":"g.Project.ModelType","expected":0,"stage":"project"},
    {"ref":"g.Plates","kind":"count","expected":2,"stage":"geometry"},
    {"ref":"g.Soil_1_1.Active","phase":"g.Phase_1","expected":false,"stage":"activation"}
  ]
}]}]
```

Báo cáo phân biệt `verified` (giá trị đã đọc khớp điều kiện cung cấp),
`missing_or_wrong` (giá trị đọc được nhưng khác điều kiện), `unreadable` (chưa đọc
chắc chắn), `unverified` (chưa có điều kiện đối chiếu). `verified` từng thuộc tính
không xác nhận toàn bộ mô hình hay độ đúng của nguồn manual.

Kế hoạch trả `keep`, `actions`, `next_step`, `executable:false`. Đây là hướng dẫn
cho planner, không phải lệnh tự thực thi. Giữ phần khớp; chẩn đoán lỗi đọc trước;
sửa phần sai sau khi đọc mới đối tượng. Không tự xóa vùng hoặc dự án chỉ vì tên
cũ không tìm thấy. `Active=None` chỉ được đọc thêm một lần rồi báo chẩn đoán,
không ép thành `False`; chuỗi/số cũng không được coi là boolean.

Mọi đổi Active vẫn cần `inspect_stage` → `verify_stage` → `set` đúng đối tượng,
phase và boolean → đọc lại xác nhận. Báo cáo tiến độ không cấp `stage_permit`,
không thay thế `verify_model`. Việc đọc/sửa từng phần không cần verify_model
hoàn tất; calculate và tuyên bố hoàn tất/đúng manual vẫn chịu guard xác minh.
API LangGraph có bộ tool nhỏ riêng; hai lệnh này thuộc đường desktop
`plaxis_commands`, chưa mở thêm quyền ghi cho API LangGraph.
