# Chat AI trong AutoCAD 2023 — bản thử 0.3.2

Plugin Windows x64/.NET Framework 4.8, bảng WinForms PaletteSet, lệnh `CHATAI`.
Chưa biên dịch hoặc chạy AutoCAD thực trong môi trường Linux phát triển.

## Cài trên Windows

1. Đóng AutoCAD 2023. Cập nhật mã nguồn ChatAI (`git pull --rebase origin main`).
2. Mở PowerShell tại thư mục mã nguồn, chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\plugins\autocad2023\install.ps1
```

Bypass chỉ áp dụng tiến trình chạy script này, không đổi chính sách máy.
Nếu AutoCAD ở ổ khác, thêm `-AutoCADPath 'D:\Autodesk\AutoCAD 2023'`.
Script dùng compiler Windows và thư viện của bản AutoCAD đã cài, không tải DLL Autodesk.
Khi cập nhật, script giữ plugin cũ trong `%LOCALAPPDATA%\ChatAI\PluginBackups`.
DLL được biên dịch vào `build`; bundle cài tại
`%APPDATA%\Autodesk\ApplicationPlugins\ChatAI2023.bundle`.

3. Mở AutoCAD, gõ `CHATAI`. Nếu chưa tự nạp, dùng `NETLOAD` chọn DLL trong bundle.
   Nếu AutoCAD hỏi tin cậy, kiểm tra đúng DLL vừa tạo rồi duyệt theo chính sách máy;
   không tắt SECURELOAD. Không hỗ trợ AutoCAD LT 2023.
4. Đăng nhập server mặc định dự phòng hoặc nhập địa chỉ server HTTPS khác.
   Plugin dùng phiên companion của API hiện có, không lưu mật khẩu/token ra file.

## Thử trên bản vẽ mới

- Chat: “Giải thích cách ghi kích thước trong AutoCAD”.
- Vẽ: “Đơn vị bản vẽ mm. Vẽ đường thẳng WCS từ (0,0,0) tới (1000,0,0)”.
- Vẽ: “Đơn vị bản vẽ mm. Vẽ đường tròn WCS tâm (500,500,0), bán kính 200”.
- Xem JSON trả về, bấm **Duyệt và vẽ JSON**. Đếm đối tượng, kiểm tra tọa độ;
  thử `U`/Undo sau mỗi nhóm trên bản vẽ thử. Plugin không tự lưu.
- Chọn đối tượng trước khi mở bảng; bật ô gửi thông tin để AI nhận tối đa 100
  handle/type/layer, tên file (không có đường dẫn) và đơn vị. Không gửi toàn bộ DWG.

## CDM ngay trong bảng CHATAI

Chuẩn bị Python 3.10+ trên Windows, đóng AutoCAD và chạy tại thư mục mã nguồn:

```powershell
git pull --rebase origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\plugins\autocad2023\setup-cdm.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\plugins\autocad2023\install.ps1
```

Script setup tạo/dùng `.venv` riêng và cài ezdxf; không cài vào Python hệ thống.
Nếu `.venv` cũ trỏ đến Python đã gỡ, script tìm Python còn chạy được, giữ thư mục
cũ dưới tên `.venv-backup-...` rồi tạo lại. Nếu không tìm được Python 3.10+,
cài Python hoặc chạy setup với `-PythonPath 'C:\duong-dan\python.exe'`.
Mở AutoCAD, gõ `CHATAI`, đăng nhập, bấm **Chọn thư mục mã nguồn ChatAI**
và chọn thư mục chứa `assistant` cùng `.venv` (không chọn thư mục bundle).

Nhập trực tiếp vào bảng chat, ví dụ:

- “Vẽ mặt bằng và mặt cắt sơ đồ CDM. Vùng chữ nhật rộng 12 m, dài 40 m,
  D=0.8 m, H=15 m, khoảng cách tim ngang 1.5 m, dọc 1.5 m. Đơn vị m.”
- “Vẽ mặt cắt sơ đồ CDM: B=10 m, L=30 m, D=0.6 m, H=12 m,
  sx=1.2 m, sy=1.5 m. Đơn vị m.” Mẫu hiện xuất kèm mặt bằng trong cùng file;
  không phải mặt cắt đầy đủ địa tầng, nền đắp và mái dốc.
- “Vẽ trắc dọc CDM, đơn vị m, hệ số phóng đứng 5.
  Điểm 1: lý trình 0, TN=2, TK=4, đầu cọc=2, H=10.
  Điểm 2: lý trình 100, TN=3, TK=5, đầu cọc=3, H=12.”

AI hỏi thêm nếu thiếu số liệu. Bổ sung vào câu tiếp theo; giữ tối đa 6 lượt hỏi/đáp
trong bộ nhớ phiên. Đổi bản vẽ hoặc đăng nhập lại sẽ xóa ngữ cảnh chat.
Xem JSON trước khi bấm **Duyệt và vẽ JSON**, chọn tên DXF mới, duyệt tạo file.
Plugin chạy bộ tạo hình học Python hiện có rồi mở DXF mới; nếu mở tự động thất bại,
dùng `OPEN` mở đường dẫn đã báo. Không sửa/chèn vào DWG đang mở, không tự lưu DWG.

Trong trắc dọc, lớp `CDM-TOP` thể hiện đầu cọc và `CDM-TOE` thể hiện mũi cọc.
Cao độ mũi = cao độ đầu − chiều sâu; tọa độ hiển thị được phóng đứng theo hệ số
đã nhập. Số liệu lý trình/cao độ không bị thay bằng tọa độ đồ họa.

### Bố trí trong vùng polyline đang có

Sau cập nhật phải đóng/mở lại AutoCAD để DLL cũ được gỡ. Tiêu đề bảng phải hiện
**Chat AI · CAD 0.3.2**; nếu không thấy, chưa chạy đúng DLL mới.

Bấm **Chọn polyline vùng CDM** hoặc gõ `CHATAIREGION`, chọn một polyline kín
trong ModelSpace. Hỗ trợ 3–500 đỉnh, cạnh thẳng, phẳng XY cao độ 0; chưa hỗ trợ
bulge/cung tròn, lỗ trong vùng hay polyline 3D. Chọn lại vùng sẽ xóa ngữ cảnh chat cũ.

Nhập: “Bố trí cọc trong vùng đã chọn. Tọa độ vùng là mm. D=0.8 m,
sx=1.5 m, sy=1.5 m, khoảng lùi từ mép cọc tới biên 0.2 m, góc lưới 0 độ.”
Không cần B/L/H khi chỉ vẽ mặt bằng. Đơn vị header được báo để tham khảo;
người dùng xác nhận đơn vị tọa độ, không tự suy từ header.
Đỉnh được đọc trực tiếp từ CAD và giữ ở máy; AI không tạo lại biên vùng.
Bộ bố trí kiểm tra cọc nằm trọn bên trong, kể cả vùng lõm; giữ tọa độ WCS.
Trước khi tạo DXF, plugin đọc lại vùng và từ chối nếu vùng đã đổi/xóa.
Kết quả là DXF mới chứa biên vùng và cọc; chưa chèn vào DWG hay sao chép toàn bộ bản vẽ.

Nếu AI vẫn trả lời sai khả năng hoặc muốn vẽ ngay không chờ API: sau khi chọn vùng,
bấm **Nhập thông số vùng · không cần AI**, nhập đơn vị vùng, D/sx/sy (m), khoảng
lùi mép cọc (m) và góc lưới (độ). Bấm **Xem kế hoạch**, rồi **Duyệt và vẽ JSON**.
Luồng này không cần đăng nhập hay gọi AI; vẫn kiểm tra vùng trước khi tạo DXF.

### Lệnh tắt

Không cần mở ứng dụng ChatAI desktop riêng. Plugin chat gọi API trực tiếp;
tạo DXF cần `.venv` đã setup. Lệnh mặt bằng không cần đăng nhập/API:

| Lệnh | Thao tác |
|---|---|
| `CDM` | Chọn polyline rồi mở bảng thông số mặt bằng, không gọi AI |
| `CDMVUNG` | Chỉ chọn/đổi vùng CDM |
| `CDMMB` | Nhập thông số cho vùng đã chọn, không gọi AI |
| `CDMMCN` | Mở sẵn yêu cầu mặt cắt; điền số liệu thay dấu … và bấm Gửi |
| `CDMTD` | Mở sẵn yêu cầu trắc dọc; điền số liệu và bấm Gửi |
| `CHATAI` | Mở bảng chat |

Mặt cắt/trắc dọc qua chat vẫn cần đăng nhập và mạng. Các lệnh không tự vẽ hoặc
đoán số liệu: xem kế hoạch rồi duyệt xuất DXF. Chưa phải công cụ chèn vào DWG.

## Giới hạn

Chưa đồng bộ bộ nhớ/lịch sử ChatAI. Vẽ trực tiếp chỉ thực thi JSON line/circle,
tối đa 100 thao tác trong một transaction; lỗi làm hủy cả nhóm. Không chạy mã LISP,
shell hoặc JSON công cụ khác. Chưa sửa/xóa đối tượng, polyline, block, dimension.
CDM nhận 4 action được phép; tối đa 10000 cọc hoặc 500 điểm trắc dọc.
Mặt bằng polyline hỗ trợ m/mm/cm/inch; các mẫu mặt cắt/trắc dọc vẫn dùng m.
Chưa đọc Excel từ bảng chat. Sơ đồ mặt cắt có ký hiệu ROAD, không dùng chiều dày ký hiệu đó làm
thông số thiết kế. Thông số CDM do người dùng cung cấp, chưa tính lún/ổn định/sức chịu tải.
Giao diện chờ API bất đồng bộ, không tự thử lại thao tác vẽ. Lỗi hiện trong bảng;
không ghi log chứa mật khẩu hoặc dữ liệu bản vẽ.

Gỡ thử: đóng AutoCAD rồi đổi tên/di chuyển bundle ra khỏi ApplicationPlugins.
