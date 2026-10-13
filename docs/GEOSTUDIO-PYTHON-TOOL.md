# GeoStudio Python trong Chat AI

Tool `geostudio_python` được đăng ký vào OnlineAutomation và router công cụ
GeoSlope. Không cần endpoint bridge. PyGeoStudio 0.4.3 dùng đọc cấu trúc/hình
học; thao tác ghi và Solve dùng API `gsi` chính thức trên bản sao mới.

## Cài trên Windows

```powershell
& '.\runtime\python\python.exe' -m pip install -r '.\requirements-geostudio.txt'
& '.\runtime\python\python.exe' -m pip install -r 'C:\Program Files\Seequent\GeoStudio 2025.2\API\requirements.txt'
```

GeoStudio cần giấy phép hợp lệ; wheel 2025.2.1 yêu cầu Python
3.12.1 đến dưới 3.13. Nguồn GSZ phải đã lưu và nằm trong whitelist.
Khởi động lại Chat AI sau cài/cập nhật.

## Phạm vi

* `inspect`: PyGeoStudio mở được dự án và bộ đọc GSZ trả inventory đã lưu.
* `update_points`: `analysis` là tên thật; `updates` là chuỗi JSON danh sách
  `{index,before,after,source}`. Index API 1-based, tọa độ mét. Đối chiếu tọa
  độ đã lưu với API trước ghi; không dùng ID XML thay index khi hai bên không
  khớp. Kiểm tra vùng tự cắt/chồng lấn rồi cập nhật từng điểm, đọc lại và Save.
* `solve`: chỉ trên mô hình SLOPE/W đã cấu hình đúng; kiểm tra
  `all_succeeded`, nạp kết quả, đọc bảng Slip (`eRawSlipFOS`, `eSlipNum`) và
  trả Fs nhỏ nhất. Các giá trị không hợp lệ khiến tool báo lỗi.

Luôn dùng `output` của update để Solve. Tool không kiểm chứng thông số với
tiêu chuẩn thiết kế thay kỹ sư. Sau đổi tọa độ, tải/nước/gia cường/miền tìm
trượt có thể cần điều chỉnh; phải kiểm tra trước tính.

## Giới hạn

Không import DXF, không tạo điểm/vùng mới, không thay vật liệu hay nước trong
tool này. Tọa độ DXF lấy bằng bộ đọc CAD rồi ghép đúng các điểm đã có.
PyGeoStudio 0.4.3 có lỗi triển khai `createRegion`, `addPoints`, `addLines`;
tool không gọi các hàm đó, không dùng SaveAs của thư viện để viết lại XML và
làm mất thuộc tính chưa hỗ trợ. Chưa xác minh native GeoStudio trên Windows
trong môi trường cloud. Nếu thư viện không đọc được phiên bản GSZ, tool phải
báo lỗi tương thích, không dựng mô hình khác thay thế.

Timeout/lỗi sau ghi hoặc Solve có thể đã tác động bản sao; không tự gửi lại
nguyên thao tác. Stop được kiểm tra giữa các RPC; không thể bảo đảm ngắt
solver native ngay giữa một RPC đang chạy. File nguồn giữ nguyên.
