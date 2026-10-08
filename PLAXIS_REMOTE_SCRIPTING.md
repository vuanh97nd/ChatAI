# Plaxis 2D Remote Scripting — ChatAI Integration

ChatAI có thể kết nối trực tiếp tới **Plaxis 2D đang chạy**, thực thi phân tích địa kỹ thuật,
và trả về kết quả số (lún, chuyển vị ngang, hệ số an toàn) ngay trong cửa sổ chat.

---

## Yêu cầu

### 1. Cài Python client

```bash
pip install plxscripting
```

### 2. Bật Remote Scripting Server trong Plaxis

1. Mở **Plaxis 2D 2024**
2. Menu **Expert → Configure remote scripting server**
3. Đặt cổng:
   - **Input port**: 10000
   - **Output port**: 10001
4. Nhấn **Start** — trạng thái hiện "Server is running"

---

## Công cụ AI: `plaxis_run_problem`

Dùng khi muốn AI **tính toán và trả về kết quả số** ngay lập tức.

| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| `project_name` | string | Tên dự án (tối đa 100 ký tự) |
| `version` | `"2d"` \| `"3d"` | Phiên bản Plaxis |
| `problem` | JSON string | Định nghĩa bài toán (xem ví dụ bên dưới) |

**Kết quả trả về:**
- `max_settlement_mm` — lún lớn nhất (mm)
- `max_horizontal_displacement_mm` — chuyển vị ngang lớn nhất (mm)
- `safety_factor` — hệ số an toàn SF (từ giai đoạn phi-c reduction)
- `phase_results` — kết quả từng giai đoạn tính toán

---

## Ví dụ bài toán hố đào (2 lớp đất)

Gửi cho AI:

> Phân tích hố đào sâu 7m, rộng 10m, tường vây BTCT dày 0.6m, chôn sâu 3m.
> Mực nước ngầm tại độ sâu 1m. Tải mặt đất q=25 kPa.
> Lớp 1 (cát pha, dày 5m): E=22000, nu=0.30, γ=18.5, c=8, φ=28
> Lớp 2 (sét, dày 8m): E=7000, nu=0.35, γ=17.0, c=30, φ=15
> Lớp 3 (cát mịn, dày 8m): E=18000, nu=0.28, γ=18.0, c=2, φ=26

AI sẽ gọi `plaxis_run_problem` với:

```json
{
  "project_name": "Ho dao 7m",
  "version": "2d",
  "problem": "{\"type\":\"excavation_pit\",\"excavation_depth\":7,\"excavation_width\":10,\"wall_thickness\":0.6,\"embedment_depth\":3,\"surcharge\":25,\"water_table_depth\":1,\"soil_layers\":[{\"name\":\"Cat pha\",\"E\":22000,\"nu\":0.30,\"gamma\":18.5,\"c\":8,\"phi\":28,\"thickness\":5},{\"name\":\"Set\",\"E\":7000,\"nu\":0.35,\"gamma\":17.0,\"c\":30,\"phi\":15,\"thickness\":8},{\"name\":\"Cat min\",\"E\":18000,\"nu\":0.28,\"gamma\":18.0,\"c\":2,\"phi\":26,\"thickness\":8}]}"
}
```

**Kết quả mẫu:**

```
Phân tích excavation_pit (2D) hoàn tất.
Lún lớn nhất: 38.4 mm
Chuyển vị ngang lớn nhất: 21.7 mm
Hệ số an toàn (SF): 1.382

Chi tiết các giai đoạn:
Thi cong tuong vay | Lún max: 2.1 mm
Dao dat | Lún max: 38.4 mm | Chuyển vị ngang max: 21.7 mm
Kiem tra on dinh SF | SF: 1.382
```

---

## Ví dụ các bài toán khác

### Ổn định mái dốc

```json
{
  "type": "slope_stability",
  "slope_angle": 35,
  "slope_height": 8,
  "analysis": "Bishop",
  "soil_layers": [
    {"name": "Dat set", "E": 12000, "nu": 0.3, "gamma": 19, "c": 20, "phi": 25, "thickness": 10}
  ]
}
```

### Lún móng nông

```json
{
  "type": "foundation_settlement",
  "footing_width": 2.5,
  "footing_depth": 1.5,
  "load": 600,
  "soil_layers": [
    {"name": "Cat pha", "E": 15000, "nu": 0.3, "gamma": 18.5, "c": 5, "phi": 28, "thickness": 4},
    {"name": "Set",     "E": 8000,  "nu": 0.35,"gamma": 17.0, "c": 15,"phi": 20, "thickness": 6}
  ]
}
```

### Tường chắn đất

```json
{
  "type": "retaining_wall",
  "wall_height": 5,
  "wall_thickness": 0.4,
  "surcharge": 20,
  "soil_layers": [
    {"name": "Cat", "E": 20000, "nu": 0.28, "gamma": 18, "c": 0, "phi": 32, "thickness": 7}
  ]
}
```

---

## Công cụ AI: `plaxis_generate_script` (chế độ tạo file)

Dùng khi **chỉ muốn lấy file script** để chạy thủ công trong Plaxis:

```
plaxis_generate_script(
  project_name="Ho dao",
  version="2d",
  problem="{...}",
  auto_run=false   # true = chạy tự động nếu Plaxis đang bật
)
```

Script được lưu vào thư mục được phép và có thể chạy qua **File → Run Script**.

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `Chưa cài plxscripting` | Thiếu thư viện | `pip install plxscripting` |
| `Không thể kết nối PLAXIS 2D tại localhost:10000` | Server chưa bật | Expert → Configure remote scripting server → Start |
| `Script lỗi khi chạy` | Bài toán không hợp lệ | Kiểm tra tham số (độ sâu, bề dày, lớp đất) |
| `Không đọc được kết quả số` | Output server lỗi | Kiểm tra port 10001 (Output port) |

---

## Cấu trúc module

```
assistant/
  plaxis_app.py       # Script generation (tạo .py file)
  plaxis_remote.py    # Remote Scripting integration (run + results)
tests/
  test_plaxis_ai.py   # Tests script generation
  test_plaxis_remote.py  # Tests remote integration
PLAXIS_REMOTE_SCRIPTING.md  # Tài liệu này
```
