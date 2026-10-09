# ChatAI xử lý BTH → SLOPE/W, GeoStudio 2025.1.1

## Mục tiêu và thứ tự dữ liệu

Người dùng gửi bảng tổng hợp xử lý, bảng chỉ tiêu tính toán, mặt cắt DXF và GSZ kết quả mẫu. Giữ nguyên mục tiêu tính ổn định; tự đọc và tra cứu trong phạm vi công việc đã được cho phép. Không xin xác nhận từng bước đọc bảng, tra cú pháp, mở nguồn hoặc kiểm tra đối tượng.

1. **BTH xử lý là nguồn chọn mặt cắt và địa tầng.** Tìm tên mặt cắt/lý trình, hố khoan, thứ tự lớp, bề dày, chiều cao đắp, phương án xử lý và giai đoạn. Không dựng từ DXF trước rồi đoán các lớp. Không lấy cột Fs có sẵn làm kết quả mới.
2. **Bảng chỉ tiêu là nguồn vật liệu.** Ghép mã lớp; giữ tên file, sheet, địa chỉ ô, đơn vị và ý nghĩa thông số. Không dùng cột của lớp khác để điền lớp thiếu.
3. **DXF là nguồn hình dạng.** Phân biệt đường tự nhiên, thiết kế, ranh giới và bản vẽ phụ. Kiểm tra handle, layer, đơn vị và phép chuyển tọa độ; không mặc định header INSUNITS luôn đúng. Không đổi hình dạng thực thành mái dốc hình thang chỉ để dùng công cụ có sẵn.
4. **GSZ được gọi là kết quả mẫu là nguồn đối chiếu cấu trúc/cách trình bày.** Không ghi đè mẫu, sao chép thư mục kết quả vào dự án mới hoặc lấy thông số khác Excel làm dữ liệu mới. Không điều chỉnh đầu vào để ép Fs bằng mẫu.

### Ghi nhận tạm thời cho hồ sơ Km 134+300

Theo chỉ dẫn của người dùng trong hồ sơ này, tạm ưu tiên các giá trị số trong `SLTT.xlsx`, sheet `BTH (2)`, làm nguồn vật liệu cho những lớp có tên tương ứng, kể cả khi thông số lưu trong GSZ mẫu khác. Giữ nguyên địa chỉ ô và đơn vị khai báo; không áp dụng lựa chọn này cho dự án khác.

Mặt cắt Km 134+300 trong `THXL LK-BL KM133-138.xlsx`, sheet `THXL`, hàng 14 có các lớp `1a` (O14: 4.5 m), `1c` (P14: 3 m), `3` (U14: 5.5 m), hố khoan tham chiếu `CH134-1` (G14). Bảng `BTH (2)` không có lớp 1a. Theo chỉ dẫn mới nhất, tạm giữ 1a theo vật liệu đang lưu trong GeoStudio: gamma 16.1 kN/m3, Co/Su 14.7 kN/m2, `UndrainedPhiZero`, φ=0; chưa thay bằng mẫu thí nghiệm. Với 1c, dùng Co VST hàng 13 (E13=15.10 kN/m2) và `UndrainedPhiZero`, φ=0. Giá trị 4.86 kN/m2 là c DST hàng 4, không dùng thay Co khi đã có VST.

Người dùng xác nhận: Co ở hàng 13 BTH là VST; hàng 4 là c DST (nhãn Co hiện tại bị nhầm; người dùng sẽ tự sửa workbook), hàng 6 là φ DST. Ưu tiên Co VST như Su với `UndrainedPhiZero`, φ=0; nếu không có Co VST thì dùng c/φ DST. Theo cập nhật hiện tại, 1c dùng E13=15.10 kN/m² làm Co; c DST 4.86 kN/m² không thay thế Co VST. Tạm lấy vật liệu 1a từ GeoStudio hiện có. Lớp 3 tiếp tục lấy Co VST từ I13=51.25 kN/m². Đất đắp D13 trống nên dùng D4=25.8 kN/m² và D6=17.1°; vùng `TD+CT` dùng cùng bộ DST của đất đắp.

Người dùng xác nhận đơn vị dung trọng `kN/m2` trong BTH là nhầm; với bài này hiểu các giá trị dung trọng BTH là `kN/m3`. Các giá trị thí nghiệm lớp 1a (E6/G6/F6) không dùng cho run hiện tại vì người dùng yêu cầu tạm dùng thông số phần mềm.

Các kết quả solve trước trong lịch sử đã bị thay bởi cập nhật mới nhất. Tạm giữ lớp 1a theo GeoStudio hiện có (γ=16.1 kN/m³, Co/Su=14.7 kN/m², `UndrainedPhiZero`, φ=0). Người dùng xác nhận hàng 13 là Co VST, hàng 4 là c DST; do đó 1c dùng Co VST E13=15.10 kN/m² (`UndrainedPhiZero`, φ=0), không dùng c DST 4.86 kN/m² khi đã có Co VST. Run ở `SolveRuns_UserUpdate_1aSoftware_1cCo486` đã gán nhầm 4.86 thành Co và không dùng làm kết quả. Run sửa đúng đã hoàn tất trong `SolveRuns_UserUpdate_1aSoftware_1cVSTCo`: DTD+CT Fs nhỏ nhất = 1.1297373567 (4,096 mặt trượt hữu hạn, slip 430); TXL Fs nhỏ nhất = 0.4745786443 (29,791 mặt trượt hữu hạn, slip 14071). Đây là kết quả đọc từ CSV trong GSZ mới; log GeoCmd và `Solve-inputs.json` nằm cùng thư mục. Không ghi đè các run trước hoặc workbook gốc.

Nếu bảng đổi tên sheet/cột hoặc dùng ô gộp, tìm theo nhãn, liệt kê sheet và đọc tiếp vùng ô. `geoslope_inspect` nhận diện một số kiểu BTH/SLTT; kết quả nhận diện không đầy đủ không có nghĩa file không có dữ liệu. Dùng `sheet` và `cell_range` để kiểm tra trực tiếp. Không hứa mọi định dạng đều tự nhận diện được.

## Công cụ hiện có

- `geoslope_inspect(path=...)`: đọc XLSX, DXF, GSZ trong thư mục được phép; không chạy ứng dụng hay thay đổi file.
- Với XLSX, trả các bảng mặt cắt và chỉ tiêu cùng địa chỉ ô; đọc vùng cụ thể để kiểm tra công thức/cache. Ô lỗi hoặc công thức chưa có cache không được đổi thành 0.
- Với DXF, `layer`/`handle` chọn đối tượng; dùng `start`/`limit` đến hết. Bulge, block, đường đứng, nhiều mặt cắt cần xử lý đúng, không tự bỏ để có một đường dễ vẽ.
- Với GSZ, chỉ đọc XML gốc `GSIData`, phân biệt vật liệu có trong thư viện và vật liệu thật sự được gán vào vùng. Đọc toàn bộ CSV mặt trượt để tìm Fs nhỏ nhất, báo rõ **kết quả đã lưu**, không phải vừa chạy Solve. Fs dương/hữu hạn vẫn chưa chứng minh hội tụ hay miền tìm trượt đủ rộng.
- `geoslope_profile(path, handle, units="m", layers=...)`: tạo DXF địa tầng mới từ bề dày đứng của BTH, không sửa DXF nguồn. Đây là bản vẽ chuẩn bị mô hình, **chưa gán vật liệu/chạy ổn định**.

Ví dụ layers (số dưới đây chỉ thuộc bộ hồ sơ Km134+300, không dùng làm mặc định cho bài khác):

```json
[
  {"code":"1a","thickness":4.5,"source":"THXL!O14"},
  {"code":"1c","thickness":3,"source":"THXL!P14"},
  {"code":"3","thickness":5.5,"source":"THXL!U14"}
]
```

## Địa tầng song song đường tự nhiên

Theo yêu cầu người dùng, khi BTH cung cấp bề dày đứng không đổi và không có ranh giới khảo sát cần ưu tiên:

`x_đáy = x_tự_nhiên`, `y_đáy_lớp_k = y_tự_nhiên − tổng(bề_dày_1…k)`.

Giữ mọi điểm gãy. Đây là dịch xuống theo phương đứng, **không phải OFFSET vuông góc**. Mỗi vùng đất được tạo giữa hai đường kế tiếp và khép biên bên. Đường thiết kế vẫn là đường riêng; dựng vùng đắp giữa thiết kế và tự nhiên, kiểm tra phần cắt/đào và giao nhau trước khi gán vật liệu. Không kéo dài miền hoặc tự đặt lớp nền dưới cùng ngoài dữ kiện được xác nhận. Nếu có ranh giới thực theo khảo sát, dùng ranh giới đó.

## Ý nghĩa Co/Su trong SLTT của người dùng

Người dùng xác nhận **Co trong SLTT.xlsx là Su** và với bài Km 134+300 yêu cầu dùng `phi=0`. Không đọc Co thành c′ chỉ vì cột tên “Lực dính”. Với mô hình không thoát nước φ=0:

- `SlopeModel = UndrainedPhiZero`;
- `StressStrain/Cohesion = Su`;
- không gán Su vào `CohesionPrime`, không cộng φ khác để tăng sức chống cắt khi đã có Co VST.

Với lớp không có Co VST trong BTH, dùng c hàng 4 và φ hàng 6 từ DST theo chỉ dẫn riêng của người dùng; nếu số liệu/đơn vị đó chưa rõ thì hỏi. Bài thoát nước khác cần c′ và φ′ được xác định đúng. Không áp ý nghĩa Co=Su hoặc lựa chọn φ=0 sang mọi file của mọi người dùng. Không tự lấy thông số từ GSZ cũ.

## Dựng và tính trong GeoStudio thực

1. Tự tìm GeoStudio đã cài qua công cụ liệt kê ứng dụng; kiểm tra phiên bản và giấy phép SLOPE/W. Không dùng bộ cài thay chương trình.
2. Tạo bản mới tại đường dẫn mới. Nhập/vẽ hình học theo dữ liệu chuẩn hóa, gán đúng vật liệu cho từng vùng. Chỉ dùng cấu trúc GSZ mẫu đã kiểm chứng; bộ sinh hình thang đơn giản cũ có XML `SLOPE_MODEL` khác cấu trúc `GSIData` của mẫu 2025.1.1, chưa được kiểm chứng tương thích và không được dùng thay bài DXF thực.
3. Thiết lập nước, tải, phương pháp và miền tìm mặt trượt từ đề/BTH/tài liệu. Không tự sao chép tải/nước/miền tìm trượt của mẫu sang mặt cắt khác. Tra chức năng thực tế trước khi dùng; không đoán API, cờ dòng lệnh hay phím tắt.
4. Nếu tự động hóa bằng giao diện, dùng kết quả kiểm tra control để thao tác; không bấm theo tọa độ cố định. Chạy kiểm tra mô hình trước Solve, sửa đúng bước lỗi, không xóa mô hình hoặc chạy lại mọi thao tác đã thực hiện.
5. Theo dõi Solve đến khi có trạng thái hoàn tất/lỗi, giữ nhật ký. Chỉ mở được file không phải đã tính xong.
6. Đọc **kết quả của phiên tính mới**, xác minh dự án/analysis và thời điểm; lưu Fs, mặt trượt nguy hiểm, phương pháp, trạng thái, hình kết quả và số liệu nguồn. Không đọc GSZ mẫu để thay cho kết quả mới. Giữ output cũ tách khỏi output mới.
7. Ghi nhớ cách xử lý có bằng chứng công cụ theo tài khoản; không lưu lời tuyên bố của AI thành bằng chứng đã Solve. Không tự chạy lại chỉ vì khôi phục hội thoại.

Chỉ hỏi khi thiếu chỉ tiêu, có nhiều phương án khác nhau không xác định được, đơn vị mâu thuẫn ảnh hưởng kết quả, cần đăng nhập/giấy phép hoặc bước cần tương tác mà công cụ không hỗ trợ. Không hỏi người dùng cú pháp lệnh, tên biến hoặc có được đọc trang tra cứu không khi quyền đã có.

## Trạng thái kiểm chứng

Bộ đọc và vẽ địa tầng đã được kiểm tra bằng các tệp người dùng cung cấp và kiểm thử Python. Chưa có GeoStudio Windows tại môi trường cloud, nên chưa kiểm chứng thao tác dựng/Solve thực tế hoặc phát hành một công cụ Solve toàn trình. Không báo tính xong cho đến khi thực hiện và xác minh trên máy có GeoStudio.
