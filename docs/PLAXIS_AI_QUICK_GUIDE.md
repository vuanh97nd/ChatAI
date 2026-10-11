# PLAXIS: hướng dẫn ngắn cho AI

Nguồn: Tutorial Manual 2D/3D **2025.1**, cập nhật 24/09/2025, do người dùng cung cấp. Đã lập chỉ mục toàn bộ 295 trang 2D và 177 trang 3D. Đây là hướng dẫn thao tác và chọn nhánh; chưa phải quy trình đã chạy kiểm chứng trên PLAXIS. Trang dưới đây là số trang PDF/manual trong hai tệp này.

## 8 bước bắt buộc

1. **Chọn bài:** xác định 2D/3D, chương, case và mục tiêu. Không trộn hai bài cùng tên “móng”.
2. **Đọc dữ kiện:** hình học, bảng đất/kết cấu, nước, biên, phase. Thiếu số thì đọc nguồn hoặc hỏi; không đoán từ tỷ lệ ảnh.
3. **Chốt hệ tọa độ:** 2D đứng Y; 3D đứng Z. Đọc đơn vị và mốc mặt đất. Giữ hoặc chuyển toàn bộ tọa độ nhất quán.
4. **Dựng:** ModelType → miền đất/borehole → vật liệu → hình học/kết cấu/interface → gán vật liệu/biên. Đọc lại sau mỗi nhóm.
5. **Mesh:** đúng cấp lưới và vùng tinh chỉnh trong bài. Đổi hình học thì tạo lưới lại.
6. **Phase:** Initial theo manual; tạo đúng phase cha; đặt Active và giá trị tải/chuyển vị/nước/thời gian. Đọc lại cả hai, không chỉ Active.
7. **Calculate:** đánh dấu phase cần tính, chạy và kiểm tra từng phase. Trạng thái thiếu/lỗi = chưa hoàn tất.
8. **Output:** đúng phase, đối tượng/vị trí, đại lượng, dấu và đơn vị. Lưu và kiểm tra file nếu được yêu cầu.

**Không bỏ bước kiểm tra vì lệnh trả OK. Không gửi lại lệnh ghi khi chưa biết lần trước đã chạy hay chưa.**

## Bài tương tự

Thay dữ liệu vào cùng quy trình khi giữ cùng loại mô hình, vai trò hình học và giả thiết. Đổi 2D/3D, drained/undrained, model đất, kiểu tải, mặt đất dốc hoặc trình tự thi công: chọn/kiểm chứng nhánh khác. Không có một script bảo đảm mọi bài tương tự đều đúng.

K0 không dùng cho mọi địa hình. Phase so sánh có thể chung cha; phase thi công kế tiếp chỉ nối tiếp nếu manual quy định. Không tự giản lược tường/neo/chống/flow/dynamics/thermal để làm bài chạy.

## Chọn nhánh đúng

### 2D

| Chương; trang | Bài và điều cần giữ |
|---|---|
| 1; 10–39 | **Settlement of a circular footing on sand**. A: móng cứng dùng chuyển vị cưỡng bức; B: móng mềm dùng plate và tải. Axisymmetric, không dùng Building. |
| 2; 40–51 | **Drained and undrained stability of an embankment**. Đắp trên nền drained/undrained là hai nhánh từ Initial; Safety từ trạng thái tương ứng, không nối thành một lịch thi công. |
| 3; 52–71 | **Submerged construction of an excavation**. Tường + interface + chống + tải; đào từng đợt, giữ nước đúng từng phase; đọc chuyển vị, lực cắt và moment. |
| 4; 72–91 | **Stabilisation of a rock slope**. Đá Hoek-Brown, khe đứt gãy, cáp, tường, đắp bù; đào/chống theo thứ tự rồi Safety. |
| 5; 92–107 | **Settlements due to tunnel construction [GSE]**. TBM: công trình → máy → độ côn → bơm vữa → lining; giữ áp lực/co ngót theo manual. |
| 6; 108–120 | **Excavation of an NATM tunnel [GSE]**. NATM: đào giảm confinement → lining tạm → đào tiếp → lining cuối; không thay bằng polygon chữ nhật. |
| 7; 121–137 | **Dry excavation using a tie back wall [ADV]**. Tường/interface/tải → đào → neo hàng 1 → đào → neo hàng 2 → đào cuối; kiểm tra nước và prestress. |
| 8; 138–144 | **Dry excavation using a tie back wall - ULS [ADV]**. Dùng mô hình bài 7, áp dụng Design approach và hệ số riêng theo manual; không nhân hệ số hai lần. |
| 9; 145–165 | **Construction of a road embankment [ADV]**. Đắp theo đợt + Consolidation theo thời gian/áp lực dư; so sánh có drain, Safety và Updated mesh. |
| 10; 166–169 | **Excavation and dewatering [ADV]**. Đào và hạ nước: đọc toàn bộ chương ngắn, phân biệt áp lực nước với việc tắt đất, không dùng Head thay mọi biên flow. |
| 11; 170–193 | **Cyclic vertical capacity and stiffness of circular underwater footing [ADV]**. Móng tròn tải chu kỳ: UDCAM-S và tích lũy chu kỳ; cần tham số/chuỗi tải đúng, không dùng MC thay thế. |
| 12; 194–203 | **Flow through an embankment [ULT]**. Flow only: thấm không ổn định rồi dài hạn; đọc head, lưu lượng và áp lực nước, không báo lún. |
| 13; 204–213 | **Potato field moisture content [ULT]**. Flow only không bão hòa: khí hậu và điều kiện mặt đất theo thời gian; đọc độ ẩm và áp lực nước. |
| 14; 214–231 | **Stability of dam under rapid drawdown [ULT]**. Gravity + thấm ban đầu → Fully coupled rút nhanh/rút chậm → mực thấp → Safety từng nhánh. |
| 15; 232–242 | **Dynamics analysis of a generator on an elastic foundation [ULT]**. Tĩnh → chạy máy Dynamic → dừng máy → so sánh damping; cần hàm tải, thời gian và biên động. |
| 16; 243–254 | **Pile driving [ULT]**. Đóng cọc Dynamic: tải xung → fading; cần HSsmall, đơn vị thời gian, bước thời gian và biên động. |
| 17; 255–270 | **Free vibration and earthquake analysis of a building [ULT]**. Xây dựng → kích thích → dao động tự do; động đất là nhánh từ phase chỉ định, dùng input và biên riêng. |
| 18; 271–284 | **Thermal expansion of a navigable lock [ULT]**. Xây âu → gia nhiệt: điều kiện nhiệt/hàm nhiệt, vật liệu nhiệt và biến dạng nhiệt. |
| 19; 285–295 | **Freeze pipes in tunnel construction [ULT]**. Ống đóng băng + flow/thermal: mô hình toàn vùng, đường nước chưa đóng băng và biên nhiệt đúng nguồn. |

### 3D

| Chương; trang | Bài và điều cần giữ |
|---|---|
| 1; 7–40 | **Foundation in overconsolidated clay**. A: móng cứng là volume Building; B: raft plate+tải; C: pile-raft với embedded beams. Không đổi sang bài móng tròn 2D. |
| 2; 41–58 | **Excavation in sand**. Hố đào 3D: walings/struts/anchors/sheet walls/tải, đủ chiều dài và kích thước XYZ, đào/chống theo phase. |
| 3; 59–70 | **Loading of a suction pile**. Suction pile: mặt cong/interface và tải nhiều hướng; các hướng tải là nhánh riêng, không cộng dồn ngoài manual. |
| 4; 71–80 | **Stability of a diaphragm wall excavation**. Tường diaphragm: đào I/II/III → bê tông lỏng → đông cứng → Safety từng trạng thái. |
| 5; 81–112 | **Phased excavation of a shield tunnel [GSE]**. TBM 3D: mặt cắt + trajectory + sequencing; máy tiến theo bước, áp lực/vữa/lining đúng từng slice. |
| 6; 113–131 | **Construction of a road embankment [ADV]**. Đắp đường 3D: Consolidation theo đợt/thời gian, so sánh drains; Safety từ trạng thái đúng. |
| 7; 132–147 | **Rapid drawdown analysis [ULT]**. Mực hồ cao → rút nhanh/chậm coupled → mực thấp → Safety từng nhánh; giữ thời gian và flow BC. |
| 8; 148–159 | **Dynamics analysis of a generator on an elastic foundation [ULT]**. Tĩnh → Dynamic chạy/dừng máy → damping; tải surface, hàm thời gian và biên hấp thụ theo manual. |
| 9; 160–177 | **Free vibration and earthquake analysis of a building [ULT]**. Xây dựng → excitation → free vibration; earthquake từ phase riêng; nhập gia tốc và biên động đúng. |

## Hai bài dễ bị trộn

**2D, chương 1, Case A — móng tròn cứng trên cát** (tr. 14–28): Axisymmetric, 15-node; miền X=0…5, Y=0…4 m; borehole tại X=0; mặt đất Y=4, đáy Y=0; Head=2 m. Sand: MC/Drained, γunsat=17, γsat=20 kN/m³, ERef=13000 kN/m², ν=0.3, cRef=1 kN/m², φ=30°, ψ=0°. Line displacement (0,4)→(1,4): X Fixed, Uy=-0.05 m. Initial K0; phase Plastic kích hoạt chuyển vị. Đọc Force-Y; manual quy định tổng lực móng = Force-Y × 2π, khoảng 588 kN trong ví dụ. Không dùng hệ số này cho mọi kết quả Axisymmetric.

**3D, chương 1, Case A — móng cứng trên sét quá cố kết** (tr. 8–24): mô hình 1/4; miền X/Y=0…75 m, mặt đất Z=0, đáy Z=-40, Head=-2 m. Mặt Building (0,0,0)→(0,18,0)→(18,18,0)→(18,0,0), extrude Z=-2. Lacustrine Clay: MC/Drained, γunsat=17, γsat=18, ERef=10000, ν=0.3, cRef=10, φ=30°, ψ=0°. Building: Linear Elastic/Non-porous, γunsat=50, ERef=30000000, ν=0.15 (đơn vị m/kN/day). Initial dùng đất sét trong vùng basement; phase Building đổi vật liệu vùng đó sang Building. Không vẽ khối này thành polygon 2D trên mặt đất.

Các số trên chỉ tái tạo ví dụ manual. Với bài người dùng khác, thay bằng dữ liệu có nguồn; không dùng số ví dụ như mặc định thiết kế.

## Lỗi: chỉ sửa bước lỗi

- `Unknown property`: chọn đúng material model rồi đọc `tabulate`; MC dùng ERef, không dùng E50Ref.
- `Invalid parameters`: đọc `signature` và đúng mode; không thử nhiều biến thể đoán mò.
- `Active` chưa rõ: đọc đúng đối tượng/phase; giữ kiểu và giá trị gốc, không ép chuỗi thành boolean.
- Readback lỗi sau ghi: đọc trạng thái mới, không tạo lại đối tượng hoặc chạy lại cả nhóm.
- Phase lỗi: đọc log, vật liệu, biên, nước, tải và mesh; không tự giảm tải/đổi model để né lỗi.
- Output thiếu: báo chưa xác minh kết quả. SumMsf chỉ dùng cho Safety; độ lún tại móng khác cực trị toàn miền.

## Tiết kiệm token

Gọi `plaxis_tutorial_guide(version, chapter)` một lần để chọn nhánh. Đọc PDF đúng trang, giữ thông số và nguồn; chỉ gửi bước hiện tại và lỗi mới cho AI. Gom lệnh độc lập thành nhóm; tính tọa độ/đổi đơn vị bằng chương trình; cache tài liệu, đọc mới trạng thái dự án. Model yếu chọn bước; validator quyết định được đi tiếp hay phải dừng.

**Khác phiên bản:** nguồn 2025.1 không chứng minh API tương thích PLAXIS 22.1. Tra cú pháp trên phiên bản đang chạy. GSE/ADV/ULT và các model/module cần kiểm tra khả năng/license thực, không tự đổi loại phân tích khi thiếu.
