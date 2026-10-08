# Bài toán test: Tính lún móng nông trên nền đất hai lớp

## Mô tả vấn đề

Tính toán **độ lún** (settlement) của một móng băng (strip footing) đặt trên nền đất gồm hai lớp: lớp cát pha phía trên và lớp sét phía dưới.

## Thông số bài toán

| Thông số           | Giá trị  | Đơn vị |
|--------------------|----------|--------|
| Chiều rộng móng B  | 4.0      | m      |
| Chiều sâu chôn móng D | 2.0   | m      |
| Tải trọng P        | 100.0    | kPa    |
| Loại phân tích     | 2D, plane strain | — |

## Địa tầng

### Lớp 1 – Cát pha (0 – 5 m)

| Thông số | Giá trị | Đơn vị |
|----------|---------|--------|
| Tên      | Cat pha | —      |
| Mô đun đàn hồi E | 18 000 | kPa |
| Hệ số Poisson ν  | 0.30   | —   |
| Trọng lượng riêng γ | 18.5 | kN/m³ |
| Lực dính kết c   | 8      | kPa |
| Góc ma sát trong φ | 28   | độ  |
| Chiều dày         | 5.0    | m   |

### Lớp 2 – Sét (5 – 12 m)

| Thông số | Giá trị | Đơn vị |
|----------|---------|--------|
| Tên      | Set deo | —      |
| Mô đun đàn hồi E | 6 000  | kPa |
| Hệ số Poisson ν  | 0.35   | —   |
| Trọng lượng riêng γ | 17.0 | kN/m³ |
| Lực dính kết c   | 20     | kPa |
| Góc ma sát trong φ | 18   | độ  |
| Chiều dày         | 7.0    | m   |

## Yêu cầu output

1. **Script Plaxis hợp lệ** — cú pháp Python đúng, không lỗi parse.
2. **Import đúng** — có `from plxscripting.easy import new_server`.
3. **Khai báo vật liệu** — tên hai lớp đất xuất hiện trong script.
4. **Khai báo tải** — có lệnh `g.lineload(` để đặt tải trọng móng.
5. **Lưới phần tử** — có `g.mesh(` để chia lưới.
6. **Tính toán** — có `g.calculate()` để chạy bài toán.
7. **Không tự chạy** — kết quả trả về `executed = False` (chỉ lưu file, không kết nối Plaxis).

## JSON đầu vào cho AI

```json
{
  "type": "foundation_settlement",
  "footing_width": 4.0,
  "footing_depth": 2.0,
  "load": 100.0,
  "soil_layers": [
    {
      "name": "Cat pha",
      "E": 18000,
      "nu": 0.30,
      "gamma": 18.5,
      "c": 8,
      "phi": 28,
      "thickness": 5.0
    },
    {
      "name": "Set deo",
      "E": 6000,
      "nu": 0.35,
      "gamma": 17.0,
      "c": 20,
      "phi": 18,
      "thickness": 7.0
    }
  ]
}
```

## Kết quả mong đợi

- `result["ok"]` là `True`
- `result["problem_type"]` là `"foundation_settlement"`
- `result["executed"]` là `False`
- Script sinh ra có thể parse bằng `ast.parse()` mà không báo `SyntaxError`
- Script chứa tên địa tầng `"Cat pha"` và `"Set deo"`
- Script chứa tải phân bố `-25.00` kPa/m (= 100 kPa / 4 m)
