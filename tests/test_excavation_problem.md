# Bài toán hố đào – Mô tả & Hướng dẫn test Plaxis

## Mô tả bài toán

**Loại bài toán:** Hố đào có tường vây (excavation_pit)

### Thông số hình học

| Thông số | Giá trị |
|---|---|
| Độ sâu hố đào (H) | 6.0 m |
| Chiều rộng hố đào (W) | 8.0 m |
| Chiều dày tường vây (t) | 0.5 m |
| Chiều sâu chôn tường (d) | 2.0 m (dưới đáy hố đào) |
| Tải trọng mặt đất sau tường (q) | 20 kPa |

### Địa tầng (3 lớp)

| Lớp | Tên | E (kPa) | ν | γ (kN/m³) | c (kPa) | φ (°) | Dày (m) |
|---|---|---|---|---|---|---|---|
| 1 | Cát pha | 20000 | 0.30 | 18.5 | 5 | 28 | 4.0 |
| 2 | Sét | 8000 | 0.35 | 17.0 | 25 | 18 | 6.0 |
| 3 | Cát mịn | 15000 | 0.28 | 18.0 | 2 | 25 | 8.0 |

### Kết quả cần tính

- Ứng suất trong đất và tường vây
- Chuyển vị ngang / lún tường
- Hệ số an toàn ổn định (SF via Phi-c reduction)

---

## JSON đầu vào cho AI

Gửi đoạn JSON sau cho AI để tạo script Plaxis:

```json
{
  "type": "excavation_pit",
  "excavation_depth": 6.0,
  "excavation_width": 8.0,
  "wall_thickness": 0.5,
  "embedment_depth": 2.0,
  "surcharge": 20.0,
  "soil_layers": [
    {"name": "Cat pha", "E": 20000, "nu": 0.30, "gamma": 18.5, "c": 5,  "phi": 28, "thickness": 4.0},
    {"name": "Set",     "E": 8000,  "nu": 0.35, "gamma": 17.0, "c": 25, "phi": 18, "thickness": 6.0},
    {"name": "Cat min", "E": 15000, "nu": 0.28, "gamma": 18.0, "c": 2,  "phi": 25, "thickness": 8.0}
  ]
}
```

---

## Hướng dẫn sử dụng

### 1. Kiểm tra Plaxis đã cài chưa

Mở Command Prompt, chạy:

```
py -c "from plxscripting.easy import new_server; print('plxscripting OK')"
```

Nếu thấy `plxscripting OK` → đã cài. Nếu lỗi `ModuleNotFoundError` → cần cài:

```
pip install plxscripting
```

### 2. Bật Remote Scripting trong Plaxis

1. Mở Plaxis 2D
2. Vào menu **Expert → Configure remote scripting server**
3. Đặt Port = `10000`, Password = (để trống)
4. Bấm **Start server**

### 3. Gửi bài toán cho AI

Trong cửa sổ chat, gõ:

> Hãy tạo script Plaxis 2D cho bài toán hố đào sau: độ sâu 6m, rộng 8m, tường vây bê tông dày 0.5m, chôn sâu 2m, tải mặt đất 20kPa. Địa tầng gồm 3 lớp: cát pha (E=20000, c=5, φ=28°, dày 4m), sét (E=8000, c=25, φ=18°, dày 6m), cát mịn (E=15000, c=2, φ=25°, dày 8m).

Hoặc dùng tool `plaxis_generate_script` với JSON ở mục trên.

### 4. Chạy script và kiểm tra kết quả

- AI trả về file `.py` → mở Plaxis → **File → Run Script** → chọn file
- Quan sát kết quả: biểu đồ chuyển vị, ứng suất, giá trị SF
- SF ≥ 1.5: an toàn; SF < 1.2: cần tăng chiều sâu chôn tường hoặc thêm thanh chống

---

## Chạy unit test (không cần Plaxis thật)

```bash
cd ChatAI
python -m pytest tests/test_plaxis_ai.py -v -k "excavation"
```

Các test này kiểm tra AI sinh script đúng cấu trúc mà không cần kết nối Plaxis thực tế.
