"""Short, source-referenced tutorial guidance. No model writes or claimed validation."""

RULES = (
    'Chọn đúng 2D/3D, chương và case. Dữ liệu người dùng thay dữ liệu ví dụ; giữ nguồn và đơn vị. '
    'Đọc mục hình học, bảng vật liệu, biên và phase của đúng bài trước khi dựng. '
    '2D đứng Y; 3D đứng Z. Không mặc định mặt đất=0. Không chuyển bài 3D thành 2D. '
    'Đọc model hiện tại → kiểm tra ModelType/units/mốc → địa tầng+nước → vật liệu+gán → '
    'hình học+kết cấu+biên → mesh → Initial → phase đúng đồ thị → calculate → trạng thái → Output. '
    'Mỗi nhóm phải đọc lại trước khi đi tiếp; Active và giá trị tải/chuyển vị là hai kiểm tra riêng. '
    'Phase so sánh có thể cùng cha; không bắt mọi phase nối tiếp. K0 không áp dụng mọi địa hình. '
    'Chỉ báo hoàn tất khi phase yêu cầu thành công và Output đúng vị trí, đại lượng, đơn vị. '
    'Safety mới báo SumMsf; móng Axisymmetric kiểm tra hệ số 2π theo đại lượng manual. '
    'Lệnh đã gửi nhưng chưa đọc lại: dừng ghi, đọc mới, không gửi lại nguyên lô. '
    'Cú pháp phải kiểm tra ở bản PLAXIS đang chạy; manual này 2025.1. '
    'Bài tương tự chỉ tái dùng khi cùng giả thiết và nhánh; thay số không đồng nghĩa đổi mô hình đất/tải.'
)

CATALOG = {'2d': [{'chapter': 1,
         'title': 'Settlement of a circular footing on sand',
         'start': 10,
         'end': 39,
         'note': 'A: móng cứng dùng chuyển vị cưỡng bức; B: móng mềm dùng plate và tải. Axisymmetric, không '
                 'dùng Building.'},
        {'chapter': 2,
         'title': 'Drained and undrained stability of an embankment',
         'start': 40,
         'end': 51,
         'note': 'Đắp trên nền drained/undrained là hai nhánh từ Initial; Safety từ trạng thái tương ứng, '
                 'không nối thành một lịch thi công.'},
        {'chapter': 3,
         'title': 'Submerged construction of an excavation',
         'start': 52,
         'end': 71,
         'note': 'Tường + interface + chống + tải; đào từng đợt, giữ nước đúng từng phase; đọc chuyển vị, '
                 'lực cắt và moment.'},
        {'chapter': 4,
         'title': 'Stabilisation of a rock slope',
         'start': 72,
         'end': 91,
         'note': 'Đá Hoek-Brown, khe đứt gãy, cáp, tường, đắp bù; đào/chống theo thứ tự rồi Safety.'},
        {'chapter': 5,
         'title': 'Settlements due to tunnel construction [GSE]',
         'start': 92,
         'end': 107,
         'note': 'TBM: công trình → máy → độ côn → bơm vữa → lining; giữ áp lực/co ngót theo manual.'},
        {'chapter': 6,
         'title': 'Excavation of an NATM tunnel [GSE]',
         'start': 108,
         'end': 120,
         'note': 'NATM: đào giảm confinement → lining tạm → đào tiếp → lining cuối; không thay bằng polygon '
                 'chữ nhật.'},
        {'chapter': 7,
         'title': 'Dry excavation using a tie back wall [ADV]',
         'start': 121,
         'end': 137,
         'note': 'Tường/interface/tải → đào → neo hàng 1 → đào → neo hàng 2 → đào cuối; kiểm tra nước và '
                 'prestress.'},
        {'chapter': 8,
         'title': 'Dry excavation using a tie back wall - ULS [ADV]',
         'start': 138,
         'end': 144,
         'note': 'Dùng mô hình bài 7, áp dụng Design approach và hệ số riêng theo manual; không nhân hệ số '
                 'hai lần.'},
        {'chapter': 9,
         'title': 'Construction of a road embankment [ADV]',
         'start': 145,
         'end': 165,
         'note': 'Đắp theo đợt + Consolidation theo thời gian/áp lực dư; so sánh có drain, Safety và Updated '
                 'mesh.'},
        {'chapter': 10,
         'title': 'Excavation and dewatering [ADV]',
         'start': 166,
         'end': 169,
         'note': 'Đào và hạ nước: đọc toàn bộ chương ngắn, phân biệt áp lực nước với việc tắt đất, không '
                 'dùng Head thay mọi biên flow.'},
        {'chapter': 11,
         'title': 'Cyclic vertical capacity and stiffness of circular underwater footing [ADV]',
         'start': 170,
         'end': 193,
         'note': 'Móng tròn tải chu kỳ: UDCAM-S và tích lũy chu kỳ; cần tham số/chuỗi tải đúng, không dùng '
                 'MC thay thế.'},
        {'chapter': 12,
         'title': 'Flow through an embankment [ULT]',
         'start': 194,
         'end': 203,
         'note': 'Flow only: thấm không ổn định rồi dài hạn; đọc head, lưu lượng và áp lực nước, không báo '
                 'lún.'},
        {'chapter': 13,
         'title': 'Potato field moisture content [ULT]',
         'start': 204,
         'end': 213,
         'note': 'Flow only không bão hòa: khí hậu và điều kiện mặt đất theo thời gian; đọc độ ẩm và áp lực '
                 'nước.'},
        {'chapter': 14,
         'title': 'Stability of dam under rapid drawdown [ULT]',
         'start': 214,
         'end': 231,
         'note': 'Gravity + thấm ban đầu → Fully coupled rút nhanh/rút chậm → mực thấp → Safety từng nhánh.'},
        {'chapter': 15,
         'title': 'Dynamics analysis of a generator on an elastic foundation [ULT]',
         'start': 232,
         'end': 242,
         'note': 'Tĩnh → chạy máy Dynamic → dừng máy → so sánh damping; cần hàm tải, thời gian và biên '
                 'động.'},
        {'chapter': 16,
         'title': 'Pile driving [ULT]',
         'start': 243,
         'end': 254,
         'note': 'Đóng cọc Dynamic: tải xung → fading; cần HSsmall, đơn vị thời gian, bước thời gian và biên '
                 'động.'},
        {'chapter': 17,
         'title': 'Free vibration and earthquake analysis of a building [ULT]',
         'start': 255,
         'end': 270,
         'note': 'Xây dựng → kích thích → dao động tự do; động đất là nhánh từ phase chỉ định, dùng input và '
                 'biên riêng.'},
        {'chapter': 18,
         'title': 'Thermal expansion of a navigable lock [ULT]',
         'start': 271,
         'end': 284,
         'note': 'Xây âu → gia nhiệt: điều kiện nhiệt/hàm nhiệt, vật liệu nhiệt và biến dạng nhiệt.'},
        {'chapter': 19,
         'title': 'Freeze pipes in tunnel construction [ULT]',
         'start': 285,
         'end': 295,
         'note': 'Ống đóng băng + flow/thermal: mô hình toàn vùng, đường nước chưa đóng băng và biên nhiệt '
                 'đúng nguồn.'}],
 '3d': [{'chapter': 1,
         'title': 'Foundation in overconsolidated clay',
         'start': 7,
         'end': 40,
         'note': 'A: móng cứng là volume Building; B: raft plate+tải; C: pile-raft với embedded beams. Không '
                 'đổi sang bài móng tròn 2D.'},
        {'chapter': 2,
         'title': 'Excavation in sand',
         'start': 41,
         'end': 58,
         'note': 'Hố đào 3D: walings/struts/anchors/sheet walls/tải, đủ chiều dài và kích thước XYZ, '
                 'đào/chống theo phase.'},
        {'chapter': 3,
         'title': 'Loading of a suction pile',
         'start': 59,
         'end': 70,
         'note': 'Suction pile: mặt cong/interface và tải nhiều hướng; các hướng tải là nhánh riêng, không '
                 'cộng dồn ngoài manual.'},
        {'chapter': 4,
         'title': 'Stability of a diaphragm wall excavation',
         'start': 71,
         'end': 80,
         'note': 'Tường diaphragm: đào I/II/III → bê tông lỏng → đông cứng → Safety từng trạng thái.'},
        {'chapter': 5,
         'title': 'Phased excavation of a shield tunnel [GSE]',
         'start': 81,
         'end': 112,
         'note': 'TBM 3D: mặt cắt + trajectory + sequencing; máy tiến theo bước, áp lực/vữa/lining đúng từng '
                 'slice.'},
        {'chapter': 6,
         'title': 'Construction of a road embankment [ADV]',
         'start': 113,
         'end': 131,
         'note': 'Đắp đường 3D: Consolidation theo đợt/thời gian, so sánh drains; Safety từ trạng thái '
                 'đúng.'},
        {'chapter': 7,
         'title': 'Rapid drawdown analysis [ULT]',
         'start': 132,
         'end': 147,
         'note': 'Mực hồ cao → rút nhanh/chậm coupled → mực thấp → Safety từng nhánh; giữ thời gian và flow '
                 'BC.'},
        {'chapter': 8,
         'title': 'Dynamics analysis of a generator on an elastic foundation [ULT]',
         'start': 148,
         'end': 159,
         'note': 'Tĩnh → Dynamic chạy/dừng máy → damping; tải surface, hàm thời gian và biên hấp thụ theo '
                 'manual.'},
        {'chapter': 9,
         'title': 'Free vibration and earthquake analysis of a building [ULT]',
         'start': 160,
         'end': 177,
         'note': 'Xây dựng → excitation → free vibration; earthquake từ phase riêng; nhập gia tốc và biên '
                 'động đúng.'}]}

def tutorial_guide(version, chapter=0):
    if version not in CATALOG:raise ValueError('version cần 2d hoặc 3d.')
    if type(chapter) is not int:raise ValueError('chapter phải là số nguyên, 0 để xem danh mục.')
    entries=CATALOG[version]
    if chapter==0:
        return {'ok':True,'manual_version':'2025.1','chapters':[
            {'chapter':e['chapter'],'title':e['title'],'pages':[e['start'],e['end']]} for e in entries],
            'note':'Chọn đúng chương/case, không chọn chỉ vì cùng từ khóa móng/đào.'}
    item=next((e for e in entries if e['chapter']==chapter),None)
    if item is None:raise ValueError('Không có chương này trong manual '+version+'.')
    return {'ok':True,'manual_version':'2025.1','source':'PLAXIS_'+version.upper()+'_1_Tutorial Manual.pdf',
            'chapter':item,'rules':RULES,'execution_verified':False,
            'note':'Hướng dẫn chọn nhánh, không thay bảng thông số/full manual. Đọc đúng trang nguồn trước khi điền dữ kiện; chưa kiểm chứng chạy thực tế.'}
