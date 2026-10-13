# Dự án GeoStudio mới từ DXF

`geostudio_create_from_dxf` tạo file GSZ mới, không mở/copy hình học của mặt
cắt cũ. Bộ dựng dùng scaffold định dạng `GSIData` của writer hiện có, xóa
toàn bộ hình học, vật liệu, phân bố và miền trượt mặc định trước khi dựng.
Đầu ra là **nháp hình học/vật liệu**, chưa phải bài toán đã cấu hình hoặc đã
tính. Không có kiểm chứng GeoStudio native trên môi trường cloud.

## Đầu vào

* `path`: DXF đã chuẩn hóa vùng trong whitelist.
* `spec`: JSON với `analysis`, `method`, `units: "m"`,
  `coordinate_source` xác nhận tỷ lệ/mốc, `materials`, `regions`.
* `regions`: danh sách `{handle, material}`. Handle phải là polyline 2D
  khép kín, không bulge, không chồng lấn. Không dùng đường mặt đất hở làm
  vùng, không tự coi mọi entity trong DXF là địa tầng.
* `materials`: mỗi vật liệu có `name`, `model`, `gamma`, `source` và
  `c_prime, phi_prime` cho MohrCoulomb hoặc `cohesion` cho UndrainedPhiZero.
  Không tự chuyển số liệu chưa rõ ý nghĩa sang hữu hiệu/không thoát nước.

Output `.inputs.json` lưu nguồn DXF, hash, spec, các cấu hình còn thiếu.
File GSZ có `IsDefined=false`; không lấy kết quả mẫu, không đặt mặc định
mực nước hoặc lực. Cần cấu hình nước, tải và miền tìm mặt trượt theo hồ sơ.

## API sau dựng

`geostudio_python` có thêm:

* `read_object`: `analysis`, `object` đúng theo API/SketchText, trả data.
* `set_properties`: `properties` JSON danh sách `{object,before,after,source}`;
  chỉ ghi khi Get khớp before, đọc lại after rồi Save bản sao. after là JSON
  Value, không mã Python. Thông số nước/tải không được đoán theo bài mẫu.

Giữ output từng bước và dùng output mới nhất cho bước sau. Chỉ Solve sau khi
GeoStudio xác nhận dự án hợp lệ và các cấu hình còn thiếu đã hoàn tất. Nếu
file cần nâng cấp hoặc thư viện không đọc được định dạng, báo đúng lỗi,
không tính trên mặt cắt cũ thay thế.

Không thêm dữ liệu công trình cụ thể vào mặc định của tool. Chưa tạo vùng
khép kín trong DXF thì phải làm bước đó trước; tool báo hạng mục thiếu,
không hỏi lại quyền xây mô hình đã được giao.
