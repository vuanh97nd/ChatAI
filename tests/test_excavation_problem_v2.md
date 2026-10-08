# Bài toán hố đào v2 – Thông số giả định chuẩn để test AI

## Mô tả bài toán

**Loại bài toán:** Hố đào có tường vây (`excavation_pit`)

### Thông số hình học

| Thông số | Ký hiệu | Giá trị |
|---|---|---|
| Độ sâu hố đào | H | 6.0 m |
| Chiều rộng hố đào | W | 8.0 m |
| Mặt đất (tham chiếu) | ±0 | 0 m |
| Chiều dày tường vây | t | 0.5 m (bê tông) |
| Chiều sâu chôn tường | d | 2.0 m (dưới đáy hố đào, tức đến -8 m) |
| Mực nước ngầm | MNN | -3.0 m so với mặt đất |
| Tải trọng mặt đất | q | 75 kPa (tải ròng, đều) |

### Địa tầng (2 lớp, Mohr-Coulomb)

| # | Tên lớp | Từ | Đến | γ (kN/m³) | γ_sat (kN/m³) | φ (°) | c (kPa) | E (kPa) | ν |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Cát (Sand) | 0 m | -4 m | 18.0 | 20.0 | 35 | 0 | 50 000 | 0.30 |
| 2 | Sét (Clay) | -4 m | -10 m | 19.0 | 21.0 | 28 | 15 | 30 000 | 0.30 |

> Ghi chú: tổng chiều dày địa tầng = 10 m; tường chôn đến -8 m (trong lớp Sét).

### Kết quả cần tính

- Ứng suất trong đất và nội lực tường vây
- Lún / chuyển vị ngang tường
- Hệ số an toàn ổn định SF (Phi-c reduction)

---

## JSON đầu vào cho AI

Gửi đoạn JSON sau cho AI để sinh script Plaxis:

```json
{
  "type": "excavation_pit",
  "excavation_depth": 6.0,
  "excavation_width": 8.0,
  "wall_thickness": 0.5,
  "embedment_depth": 2.0,
  "surcharge": 75.0,
  "water_table_depth": 3.0,
  "soil_layers": [
    {
      "name": "Cat",
      "E": 50000,
      "nu": 0.30,
      "gamma": 18.0,
      "gamma_sat": 20.0,
      "c": 0,
      "phi": 35,
      "thickness": 4.0
    },
    {
      "name": "Set",
      "E": 30000,
      "nu": 0.30,
      "gamma": 19.0,
      "gamma_sat": 21.0,
      "c": 15,
      "phi": 28,
      "thickness": 6.0
    }
  ]
}
```

---

## Checklist xác minh script

Script hợp lệ cần đủ các yếu tố sau:

- [ ] Import `from plxscripting.easy import new_server`
- [ ] Định nghĩa vật liệu đất (`g.soilmat()`) cho từng lớp
- [ ] `gammaSat` đúng theo từng lớp (20.0 và 21.0)
- [ ] Khai báo mực nước (`g.setwaterlevel(...)`) tại -3 m
- [ ] Tường vây `g.plate()` + `g.platemat()`
- [ ] Tải trọng `g.uniformload(...)` với q = 75 kPa
- [ ] Giai đoạn đào đất `Dao dat`
- [ ] Giai đoạn kiểm tra ổn định `PhiCReduction`
- [ ] `g.calculate()` ở cuối
- [ ] Cú pháp Python hợp lệ (parse được bằng `ast.parse`)
