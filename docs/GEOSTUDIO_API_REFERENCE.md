# GeoStudio API Reference cho Chat AI

Tài liệu tổng hợp các phương thức lập trình/tự động hóa GeoStudio, dùng làm ngữ cảnh cho chat AI khi hỗ trợ người dùng phân tích ổn định mái dốc.

---

## 1. Tổng quan các cách tự động hóa GeoStudio

| Phương thức | Phiên bản | Mục đích |
|---|---|---|
| **GeoCmd.exe** (command line) | Mọi phiên bản | Batch solve, upgrade file, xuất báo cáo |
| **GeoStudio Scripting API** (Python/JS/C#) | ≥ 2025.1 | Tạo/sửa mô hình, chạy solve, đọc kết quả từ bên trong GeoStudio |
| **PyGeoStudio** (thư viện Python bên thứ 3) | Mọi phiên bản | Đọc/sửa file .gsz bên ngoài GeoStudio, chạy solver, nghiên cứu tham số |
| **Đọc/ghi XML trực tiếp** | Mọi phiên bản | Thao tác XML bên trong .gsz (ZIP) không qua GeoStudio |

---

## 2. GeoCmd – Command Line Interface

### Vị trí
```
C:\Program Files\Seequent\GeoStudio 2025.2\bin\GeoCmd.exe
```
(Đường dẫn thay đổi theo phiên bản cài đặt. Thêm vào PATH để gọi trực tiếp.)

### Cú pháp cơ bản
```bash
GeoCmd.exe <file.gsz> [options]
```

### Chức năng chính
- **Solve**: chạy phân tích cho một hoặc nhiều analysis trong file .gsz
- **Upgrade**: nâng cấp file .gsz từ phiên bản cũ
- **Report**: xuất báo cáo kết quả

### Batch processing
```bash
# Solve nhiều file
for %%f in (*.gsz) do GeoCmd.exe "%%f" /solve
```

> **Lưu ý**: Tài liệu chi tiết cú pháp GeoCmd nằm trong Help của GeoStudio (Help → GeoStudio Help → Scripting) hoặc Seequent Knowledge Base. Cần kiểm tra trực tiếp vì cú pháp thay đổi theo phiên bản.

---

## 3. GeoStudio Scripting API – `gsi` (chính thức, ≥ 2025.1)

### Giới thiệu
- Module Python chính thức: `import gsi` (cài từ wheel `gsi-2025.2.1-py3-none-any.whl`)
- Yêu cầu: Python 3.12.x, GeoStudio có license hợp lệ đang chạy nền
- Giao tiếp qua gRPC giữa script Python và GeoStudio service
- GeoStudio 2025.2 thêm: `QueryResultsAtCoordinates`, giảm thời gian solve từ script

### Cài đặt
```bash
pip install -r "C:\Program Files\Seequent\GeoStudio 2025.2\API\requirements.txt"
```

### Import chuẩn
```python
import os
import grpc
from google.protobuf.json_format import MessageToDict
import gsi
```

### 3.1. Mở/đóng Project
```python
project = gsi.OpenProject(r"C:\Path\To\Project.gsz")
# ... thao tác ...
project.Close()
```

Cách an toàn (khuyến nghị):
```python
project = None
try:
    project = gsi.OpenProject(r"C:\Path\To\Project.gsz")
    # ... thao tác ...
except Exception as e:
    print(f"Lỗi: {e}")
finally:
    if project is not None:
        project.Close()
```

### 3.2. Cấu trúc đường dẫn đối tượng (Object Path)
```python
# Vật liệu
'Materials["Upper Soil"]'
'Materials["Upper Soil"].UnitWeight'

# Vùng hình học
'CurrentAnalysis.GeometryItems.Regions[1].Material'

# Mặt nước ngầm
'CurrentAnalysis.Objects.PiezometricSurfaces["Piezometric Line"]'
```

**Quy tắc**: dùng `["tên"]` cho tên đối tượng, `.thuộc_tính` cho thuộc tính, `[n]` (1-based) cho chỉ mục mảng.

### 3.3. Đọc dữ liệu – GET
```python
# Đọc toàn bộ thuộc tính vật liệu
get_req = gsi.GetRequest(
    analysis="SLOPE/W Analysis",
    object='Materials["Đất đắp"]'
)
response = project.Get(get_req)
props = MessageToDict(response.data.struct_value)

# Đọc một thuộc tính cụ thể
get_req = gsi.GetRequest(
    analysis="SLOPE/W Analysis",
    object='Materials["Đất đắp"].UnitWeight'
)
response = project.Get(get_req)
uw = response.data.number_value
```

### 3.4. Ghi dữ liệu – SET
```python
# Đổi một thuộc tính
set_req = gsi.SetRequest(
    analysis="SLOPE/W Analysis",
    object='Materials["Đất đắp"].UnitWeight',
    data=gsi.Value(number_value=19.0)
)
project.Set(set_req)

# Đổi nhiều thuộc tính cùng lúc
get_req = gsi.GetRequest(analysis="SLOPE/W Analysis", object='Materials["Đất đắp"]')
current = project.Get(get_req).data.struct_value
current.update({"UnitWeight": 19.0, "Cohesion": 10.0, "Phi": 25.0})
new_data = gsi.Value()
new_data.struct_value.update(current)
set_req = gsi.SetRequest(
    analysis="SLOPE/W Analysis",
    object='Materials["Đất đắp"]',
    data=new_data
)
project.Set(set_req)
```

**Kiểu dữ liệu:**
```python
gsi.Value(number_value=18.5)       # Số
gsi.Value(string_value="MohrCoulomb")  # Chuỗi
gsi.Value(bool_value=True)         # Boolean
```

### 3.5. Thêm/xóa đối tượng – ADD/DELETE
```python
# Thêm đối tượng mới
add_req = gsi.AddRequest(
    analysis="SLOPE/W Analysis",
    object="Materials",        # Tên đối tượng mới
    data=gsi.Value(...)
)
response = project.Add(add_req)

# Xóa đối tượng
del_req = gsi.DeleteRequest(
    analysis="SLOPE/W Analysis",
    object='Materials["Đất cũ"]',
    force_delete=False  # True: xóa ngay cả khi có tham chiếu
)
project.Delete(del_req)
```

### 3.6. Chạy Solver – SolveAnalyses
```python
# Solve một analysis
solve_req = gsi.SolveAnalysesRequest(analyses=["SLOPE/W Analysis"])
project.SolveAnalyses(solve_req)

# Solve với dependency
solve_req = gsi.SolveAnalysesRequest(
    analyses=["Transient Analysis"],
    solve_dependencies=True  # Mặc định True
)
project.SolveAnalyses(solve_req)

# Solve đến step cụ thể
solve_req = gsi.SolveAnalysesRequest(
    analyses=["Transient Analysis"],
    step_number=5
)
project.SolveAnalyses(solve_req)

# Kiểm tra kết quả solve
response = project.SolveAnalyses(solve_req)
# response.all_succeeded: bool
# response.completion_status: dict{analysis_name: {succeeded, error_message}}
```

### 3.7. Đọc kết quả – QueryResults

**Bước 1: Load kết quả vào bộ nhớ**
```python
load_req = gsi.LoadResultsRequest(analysis="SLOPE/W Analysis")
project.LoadResults(load_req)
```

**Bước 2: Kiểm tra kết quả có sẵn (tùy chọn)**
```python
avail_req = gsi.QueryResultsAvailabilityRequest(analysis="SLOPE/W Analysis")
response = project.QueryResultsAvailability(avail_req)
has_results = response.has_results  # True/False
```

**Bước 3: Truy vấn kết quả**
```python
import numpy as np

query_req = gsi.QueryResultsRequest(
    analysis="SLOPE/W Analysis",
    step=1,
    table=gsi.ResultType.Nodes,  # Nodes, Elements, Slip, CriticalSlip, Column...
    dataparams=[
        gsi.DataParamType.eXCoord,
        gsi.DataParamType.eYCoord,
        gsi.DataParamType.eWaterPressureHead
    ]
)
response = project.QueryResults(query_req)

x = np.array(response.results[gsi.DataParamType.eXCoord].values)
y = np.array(response.results[gsi.DataParamType.eYCoord].values)
pwp = np.array(response.results[gsi.DataParamType.eWaterPressureHead].values)
```

**Truy vấn kết quả tại tọa độ cụ thể (2025.2)**
```python
query_req = gsi.QueryResultsAtCoordinatesRequest(
    analysis="SLOPE/W Analysis",
    step=1,
    dataparams=[gsi.DataParamType.eWaterPressureHead],
    points=[gsi.Point(x=25.0, y=2.0)]
)
response = project.QueryResultsAtCoordinates(query_req)
```

**Truy vấn metadata bảng kết quả**
```python
info_req = gsi.QueryTableParamsInfoRequest(
    analysis="SLOPE/W Analysis",
    table=gsi.ResultType.Nodes
)
response = project.QueryTableParamsInfo(info_req)
for p in response.params_info:
    print(f"{p.key}: {p.display} ({p.units})")
```

### 3.8. Bảng kết quả (ResultType)

| Enum | Số | Mô tả |
|---|---|---|
| `Nodes` | 1000 | Nút mesh |
| `Elements` | 1002 | Phần tử mesh (1D + 2D) |
| `Gauss` | 1003 | Điểm Gauss |
| `Time` | 1005 | Bảng thời gian |
| `Slip` | 1013 | **Mặt trượt SLOPE/W** |
| `CriticalSlip` | 1014 | **Mặt trượt nguy hiểm nhất** |
| `Column` | 1015 | Dữ liệu cột mặt trượt |
| `Intercolumn` | 1016 | Dữ liệu giữa các cột |
| `LambdaFOS` | 1017 | Lambda-FOS |
| `Reinforcement` | 1018 | Cốt/neo trên mặt trượt |
| `Probabilistic` | 1024 | Kết quả xác suất |

### 3.9. DataParamType quan trọng cho SLOPE/W

| Enum | Ý nghĩa |
|---|---|
| `eViewSlipFOS` | **Hệ số ổn định Fs** |
| `eSlipNum` | Số hiệu mặt trượt |
| `eSlipCenterX/Y` | Tâm mặt trượt tròn |
| `eSlipRadius` | Bán kính mặt trượt |
| `eSlipWeight` | Trọng lượng khối trượt |
| `eSlipVolume` | Thể tích khối trượt |
| `eResistingMoment` | Moment chống trượt |
| `eActivatingMoment` | Moment gây trượt |
| `eResistingForce` | Lực chống trượt |
| `eActivatingForce` | Lực gây trượt |
| `eSlipFOSMean` | Fs trung bình (xác suất) |
| `eSlipFOSMin` | Fs nhỏ nhất |
| `eSlipFOSMax` | Fs lớn nhất |
| `eSlipProbOfFailure` | Xác suất phá hoại |
| `eSlipReliabilityIndex` | Chỉ số tin cậy |
| `eStabilityFactor` | Hệ số ổn định |
| `eBaseCohesion` | Lực dính đáy cột |
| `eBasePhi` | Góc ma sát đáy cột |
| `eBaseNormalStress` | Ứng suất pháp đáy |
| `eShearStrength` | Sức chống cắt |
| `eShearMob` | Ứng suất cắt huy động |
| `eColumnWeight` | Trọng lượng cột |
| `ePoreWaterForce` | Lực nước lỗ rỗng |
| `eBaseNormalForce` | Lực pháp đáy |
| `eUnitWeight` | Dung trọng |
| `eSlopeCohesion` | Lực dính SLOPE |
| `eSlopePhi` | Góc ma sát SLOPE |

### 3.10. Project Interface – Tổng hợp phương thức

| Phương thức | Request | Response | Mô tả |
|---|---|---|---|
| `project.Get(req)` | GetRequest | GetResponse | Đọc thuộc tính đối tượng |
| `project.Set(req)` | SetRequest | SetResponse | Ghi thuộc tính |
| `project.Add(req)` | AddRequest | AddResponse | Thêm đối tượng mới |
| `project.Delete(req)` | DeleteRequest | DeleteResponse | Xóa đối tượng |
| `project.SolveAnalyses(req)` | SolveAnalysesRequest | SolveAnalysesResponse | Chạy solver |
| `project.LoadResults(req)` | LoadResultsRequest | LoadResultsResponse | Nạp kết quả vào RAM |
| `project.QueryResults(req)` | QueryResultsRequest | QueryResultsResponse | Truy vấn kết quả |
| `project.QueryResultsAtCoordinates(req)` | QueryResultsAtCoordinatesRequest | QueryResultsAtCoordinatesResponse | Kết quả tại tọa độ |
| `project.QueryResultsAvailability(req)` | QueryResultsAvailabilityRequest | QueryResultsAvailabilityResponse | Kiểm tra có kết quả |
| `project.QueryTableParamsInfo(req)` | QueryTableParamsInfoRequest | QueryTableParamsInfoResponse | Metadata bảng kết quả |

### 3.11. Ví dụ hoàn chỉnh – Đổi vật liệu → Solve → Đọc Fs

```python
import gsi
from google.protobuf.json_format import MessageToDict
import numpy as np

project = None
try:
    project = gsi.OpenProject(r"C:\Data\MySlope.gsz")
    analysis = "SLOPE/W Analysis"
    
    # Đổi dung trọng
    project.Set(gsi.SetRequest(
        analysis=analysis,
        object='Materials["Đất đắp"].UnitWeight',
        data=gsi.Value(number_value=19.0)
    ))
    
    # Solve
    solve_resp = project.SolveAnalyses(
        gsi.SolveAnalysesRequest(analyses=[analysis])
    )
    
    # Load và đọc kết quả mặt trượt nguy hiểm
    project.LoadResults(gsi.LoadResultsRequest(analysis=analysis))
    
    query = gsi.QueryResultsRequest(
        analysis=analysis,
        step=1,
        table=gsi.ResultType.CriticalSlip,
        dataparams=[gsi.DataParamType.eViewSlipFOS]
    )
    resp = project.QueryResults(query)
    fs_values = resp.results[gsi.DataParamType.eViewSlipFOS].values
    print(f"Fs nhỏ nhất = {min(fs_values):.4f}")
    
except Exception as e:
    print(f"Lỗi: {e}")
finally:
    if project:
        project.Close()
```

### 3.12. Workflow đã kiểm chứng – Tạo .gsz → Upgrade → Solve → Đọc Fs

**Quan trọng**: File .gsz tạo bằng XML (từ `geoslope_xldy_writer.py`) cần được **upgrade** trước khi solve. GeoStudio 2025.x yêu cầu mesh metadata mà chỉ có sau khi upgrade.

```bash
# Bước 1: Tạo .gsz bằng XML writer (Python)
# Bước 2: Upgrade
GeoCmd.exe /upgrade /out:"output_dir" "input.gsz"
# Bước 3: Solve (GeoCmd hoặc GSI API đều được)
GeoCmd.exe /solve "output_dir/input.gsz"
# Bước 4: Đọc kết quả bằng GSI API
```

```python
import gsi

project = gsi.OpenProject(r"path\to\upgraded_solved.gsz")
AN = "Slope Stability - KmXX - No Treatment"

# Phải gọi LoadResults TRƯỚC khi QueryResultsAvailability
project.LoadResults(gsi.LoadResultsRequest(analysis=AN))

avail = project.QueryResultsAvailability(
    gsi.QueryResultsAvailabilityRequest(analysis=AN))
# avail.has_results == True

resp = project.QueryResults(gsi.QueryResultsRequest(
    analysis=AN, step=1,
    table=gsi.ResultType.CriticalSlip,
    dataparams=[gsi.DataParamType.eViewSlipFOS]
))
fs = list(resp.results[gsi.DataParamType.eViewSlipFOS].values)
print(f"Fs = {fs[0]:.4f}")  # Ví dụ: 0.5717

project.Close()
```

**Lưu ý quan trọng:**
- `LoadResults()` phải gọi **trước** `QueryResultsAvailability()`, nếu không `has_results` sẽ là `False`
- Khi đọc Materials không cần `analysis` param, nhưng khi Get/Set cần truyền đúng tên analysis
- `Get(object='Analyses')` và `Get(object='Materials')` (không có analysis) sẽ lỗi "Missing analysis" — phải truyền analysis name
- Solve qua GSI API cũng hoạt động sau khi upgrade (không bắt buộc dùng GeoCmd)
- Fs max rất lớn (overflow) ở bảng Slip là bình thường — mặt trượt nông không cắt đất yếu
- **`NewProject()` không thể tạo Analysis mới** — GSI API chỉ sửa/đọc project đã có analysis. Phải tạo bằng XML writer hoặc GUI
- Property name cho UndrainedPhiZero: `UndrainedShearStrengthUI` (không phải `Cohesion` hay `Su`)
- Property name cho MohrCoulomb: `CohesionPrime`, `PhiPrime`, `UnitWeight`

**Kết quả test đã kiểm chứng (2026-10-13):**
- Nền đắp h=5m, đất yếu 10m, Su=8kPa → **Fs = 0.5717**
- Tăng Su=15kPa qua API → re-solve → **Fs = 0.8996**

### Tài liệu gốc (đã copy vào project)
- [gsi_scripting_api_guide.md](gsi_scripting_api_guide.md) — Hướng dẫn đầy đủ + ví dụ
- [gsi_project_protocol.md](gsi_project_protocol.md) — Protocol reference (Request/Response)
- [gsi_all_types.md](gsi_all_types.md) — ResultType, UnitCategory, Point
- [gsi_dataparam_types.md](gsi_dataparam_types.md) — Toàn bộ DataParamType (600+ enum)

---

## 4. PyGeoStudio – Thư viện Python bên thứ 3

**Phiên bản**: 0.4.3+ | **Cài đặt**: `pip install PyGeoStudio`
**Tài liệu**: https://pygeostudio.readthedocs.io | **Mã nguồn**: https://github.com/MoiseRousseau/PyGeoStudio

### 4.1. Mở và lưu file

```python
import PyGeoStudio as pgs

# Mở file .gsz
geofile = pgs.GeoStudioFile("project.gsz")

# Xem cấu trúc
geofile.showAnalysisTree()   # In cây analysis (ID, tên, parent)
geofile.showMaterials()       # Danh sách vật liệu (detail=0 tóm tắt, detail=1 chi tiết)
geofile.showGeometries()      # Danh sách hình học
geofile.showDatasets()        # Danh sách dataset
geofile.showFunctions()       # Danh sách hàm
geofile.showReinforcements()  # Danh sách cốt/neo

# Lưu
geofile.save()                           # Ghi đè file gốc
geofile.saveAs("new_project.gsz")        # Lưu bản mới (compresslevel=0..9)
```

### 4.2. GeoStudioFile – Class chính

| Phương thức | Tham số | Mô tả |
|---|---|---|
| `GeoStudioFile(path)` | `path` (str) | Mở file .gsz |
| `getAnalysisByID(ID)` | `ID` (int) | Lấy analysis theo ID |
| `getAnalysisByName(name)` | `name` (str) | Lấy analysis theo tên |
| `getMaterialByID(ID)` | `ID` (int) | Lấy vật liệu theo ID |
| `getMaterialByName(name)` | `name` (str) | Lấy vật liệu theo tên |
| `getReinforcementByID(ID)` | `ID` (int) | Lấy reinforcement theo ID |
| `getReinforcementByName(name)` | `name` (str) | Lấy reinforcement theo tên |
| `getDatasetByName(name)` | `name` (str) | Lấy dataset theo tên |
| `getGeometryByID(ID)` | `ID` (int) | Lấy geometry theo ID |
| `createNewDataset(name, parameters)` | `name` (str), `parameters` (list) | Tạo dataset mới |
| `save()` | – | Ghi lại file gốc |
| `saveAs(f_out, compresslevel=5)` | `f_out` (str), `compresslevel` (int) | Lưu bản mới |

### 4.3. Analysis

```python
analysis = geofile.getAnalysisByName("Slope Stability")
```

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `ID` | int | Chỉ mục analysis |
| `Name` | str | Tên analysis |
| `Kind` | str | Loại: `"SEEP"` hoặc `"SLOPE"` |
| `Description` | str | Mô tả |
| `ParentID` | int | ID analysis cha |
| `Method` | str | Phương pháp (Bishop, Spencer...) |
| `Geometry` | Geometry | Đối tượng hình học |
| `Context` | Context | Phân bố vật liệu và biên |
| `Results` | Results | Kết quả phân tích |
| `TimeIncrements` | TimeIncrements | Thiết lập bước thời gian |

| Phương thức | Mô tả |
|---|---|
| `setGeometry(geom)` | Gán hình học mới |
| `setContext(context)` | Gán phân bố vật liệu/biên mới |
| `showProblem()` | Vẽ sơ đồ mô hình |

### 4.4. Material

```python
mat = geofile.getMaterialByName("Dam fill")
```

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `ID` | int | ID vật liệu |
| `Name` | str | Tên |
| `Color` | Color | Màu RGB |
| `SeepModel` | str | Mô hình thủy lực: `"SatOnly"`, `"SatUnsat"` |
| `SlopeModel` | str | Mô hình địa kỹ thuật SLOPE (VD: `"MohrCoulomb"`) |
| `StressModel` | str | Mô hình SIGMA (VD: `"LinearElastic"`) |
| `Hydraulic` | MaterialHydraulicFunction | Thuộc tính thủy lực |
| `StressStrain` | MaterialStressStrain | Thuộc tính cơ học |
| `Thermal` | MaterialThermalFunction | Thuộc tính nhiệt |

Truy cập bằng toán tử `[]`:
```python
mat["SlopeModel"]                        # → "MohrCoulomb"
mat["Hydraulic"]["KSat"] = 1e-6          # Đổi hệ số thấm bão hòa
mat["StressStrain"]["CohesionPrime"]     # Lực dính hữu hiệu c'
mat["StressStrain"]["PhiPrime"]          # Góc ma sát hữu hiệu φ'
mat["StressStrain"]["UnitWeight"]        # Dung trọng
```

#### MaterialHydraulicFunction (`mat["Hydraulic"]`)

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `KSat` | float | Hệ số thấm bão hòa |
| `VolWC` | float | Hàm lượng nước thể tích bão hòa |
| `Beta` | float | Hệ số nén |
| `KFn` | Function | Hàm hệ số thấm (SatUnsat) |
| `VolWCFn` | Function | Đường cong giữ nước (SatUnsat) |

#### MaterialStressStrain (`mat["StressStrain"]`)

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `UnitWeight` | float | Dung trọng (kN/m³) |
| `CohesionPrime` | float | Lực dính hữu hiệu c' (kPa) |
| `PhiPrime` | float | Góc ma sát φ' (°) |
| `YoungsPrimeModulus` | float | Mô đun Young E' (SIGMA) |
| `EffectivePoissonsRatio` | float | Hệ số Poisson ν' (SIGMA) |
| `Rf` | float | Tỷ số phá hoại |
| `OCRatio` | float | Hệ số quá cố kết OCR |
| `InitVoidRatio` | float | Hệ số rỗng ban đầu |
| `GeologicalStrengthIndex` | float | GSI (đá) |

#### Function (hàm dữ liệu)

```python
kfn = mat["Hydraulic"]["KFn"]
x_data = kfn.getXData()      # Mảng X (VD: áp lực nước lỗ rỗng)
y_data = kfn.getYData()      # Mảng Y (VD: hệ số thấm)
kfn.setYData(new_y_array)    # Cập nhật giá trị Y
```

### 4.5. Geometry

```python
geometry = geofile.getGeometryByID(1)
geometry.draw()                          # Vẽ hình học

points = geometry["Points"]
points[0] += [-1, -1]                   # Dịch chuyển điểm

geometry.addRegions([2, 5, 4])           # Thêm vùng từ ID điểm
```

### 4.6. Context (phân bố vật liệu & biên)

```python
context = analysis["Context"]
```

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `GeometryUsesMaterials` | dict | `{"region_name": material_id, ...}` |
| `HydraulicBCDistribution` | dict | Phân bố điều kiện biên thủy lực |

### 4.7. Chạy Solver từ Python

```python
import PyGeoStudio as pgs

geofile = pgs.GeoStudioFile("project.gsz")
analysis = geofile.getAnalysisByName("Slope Stability")

# Chạy GeoStudio solver
pgs.run(geofile, analyses_to_solve=[analysis])
```

> **Yêu cầu**: GeoStudio đã cài đặt và có license hợp lệ trên máy.

### 4.8. Đọc kết quả

```python
results = analysis["Results"]
T, PWP = results.getVariablesVsTime(
    "PoreWaterPressure",
    locations=[[25, 2]]    # Tọa độ [x, y]
)
```

> **Hạn chế**: Đọc kết quả hiện chỉ hỗ trợ SEEP (thí nghiệm). SLOPE chưa hỗ trợ qua PyGeoStudio.

### 4.9. Ví dụ hoàn chỉnh – Nghiên cứu tham số

```python
import PyGeoStudio as pgs
import matplotlib.pyplot as plt

geofile = pgs.GeoStudioFile("Rapid drawdown.gsz")
mat = geofile.getMaterialByName("Dam fill")
Kfunction = mat["Hydraulic"]["KFn"]

Ksats = [1e-7, 1e-6, 1e-5, 1e-4]
results_list = []

for new_Ksat in Ksats:
    actual_relK = Kfunction.getYData()
    actual_Ksat = Kfunction.getYData()[0]
    Kfunction.setYData(new_Ksat / actual_Ksat * actual_relK)
    
    geofile.save()
    analysis = geofile.getAnalysisByName("2 - Instantaneous drawdown")
    pgs.run(geofile, analyses_to_solve=[analysis])
    
    T, PWP = analysis["Results"].getVariablesVsTime(
        "PoreWaterPressure", locations=[[25, 2]]
    )
    results_list.append((T, PWP, new_Ksat))

fig, ax = plt.subplots()
for T, PWP, Ksat in results_list:
    ax.plot(T, PWP, label=f"Ksat = {Ksat}")
ax.legend()
ax.set_ylabel("PoreWaterPressure")
ax.set_xlabel("Time (s)")
plt.show()
```

---

## 5. Đọc/ghi GSZ trực tiếp (XML trong ZIP)

File `.gsz` là **ZIP** chứa XML. Cấu trúc phiên bản 2025.x dùng `GSIData` root element (khác `SLOPE_MODEL` của bộ sinh cũ).

### Đọc
```python
import zipfile
import xml.etree.ElementTree as ET

with zipfile.ZipFile("project.gsz", "r") as zf:
    xml_name = [n for n in zf.namelist() if n.endswith(".xml")][0]
    tree = ET.parse(zf.open(xml_name))
    root = tree.getroot()
```

### Cấu trúc XML chính (GSIData, phiên bản 11.x)
```xml
<GSIData Version="11.08">
  <Materials>
    <Material ID="1" Name="Đất đắp" SlopeModel="MohrCoulomb">
      <StressStrain>
        <UnitWeight>18.0</UnitWeight>
        <CohesionPrime>15.0</CohesionPrime>
        <PhiPrime>20.0</PhiPrime>
      </StressStrain>
    </Material>
  </Materials>
  <Geometry>
    <Points>
      <Point ID="1" X="0" Y="0"/>
    </Points>
    <Lines>
      <Line ID="1" PointIDs="1 2"/>
    </Lines>
    <Regions>
      <Region ID="1" MaterialID="1" LineIDs="1 2 3 4"/>
    </Regions>
  </Geometry>
  <Analyses>
    <Analysis ID="1" Name="SLOPE/W" Kind="SLOPE" Method="Bishop">
      <SlipSurface Type="Circular"/>
    </Analysis>
  </Analyses>
</GSIData>
```

> **Lưu ý quan trọng**: Cấu trúc XML khác nhau đáng kể giữa các phiên bản GeoStudio. Luôn dùng file mẫu thật (GSZ mẫu) làm chuẩn, không đoán tag/attribute.

### Ghi
```python
import io, zipfile
from xml.etree import ElementTree as ET

ET.indent(root, space="  ")
xml_buf = io.BytesIO()
ET.ElementTree(root).write(xml_buf, encoding="utf-8", xml_declaration=True)

with open("new_project.gsz", "wb") as f:
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.xml", xml_buf.getvalue())
```

---

## 6. Trạng thái tính năng và hạn chế

### PyGeoStudio
| Tính năng | Trạng thái |
|---|---|
| Mở/ghi file .gsz | ✅ Hoàn chỉnh |
| Chạy GeoStudio solver | ✅ Hoàn chỉnh |
| Nghiên cứu tham số | ✅ Hoàn chỉnh |
| Sửa hình học (điểm, đường, vùng) | ✅ Hoàn chỉnh |
| Sửa phân bố vật liệu | ✅ Hoàn chỉnh |
| Thuộc tính thủy lực | ✅ Hoàn chỉnh |
| Giao diện hàm (vật liệu, biên) | ✅ Hoàn chỉnh |
| Thuộc tính cốt/neo | ✅ Hoàn chỉnh |
| Xuất kết quả VTU (Paraview) | ✅ Hoàn chỉnh |
| Thuộc tính địa kỹ thuật | ⚠️ Chỉ Mohr-Coulomb |
| Đọc kết quả analysis | ⚠️ Chỉ SEEP (thí nghiệm) |
| Truy cập mesh | ⚠️ Một phần |
| Tạo đối tượng mới từ đầu | ❌ Chưa hỗ trợ |
| Phân tích Bayes/DOE | ❌ Kế hoạch |

### GeoStudio Scripting API (2025.2)
| Tính năng | Trạng thái |
|---|---|
| Tạo/sửa mô hình Python | ✅ |
| Chạy solver | ✅ (cần upgrade file trước nếu tạo bằng XML) |
| Đọc kết quả | ✅ (LoadResults trước QueryResultsAvailability) |
| Truy vấn mesh tại tọa độ | ✅ (2025.2) |
| Mở file tạo bằng XML writer | ✅ (đã kiểm chứng với GSIData 11.08) |
| Tài liệu API chi tiết từ bên ngoài | ❌ Chỉ xem trong GeoStudio Help |

---

## 7. Tài liệu tham khảo

- **GeoStudio Help (trong ứng dụng)**: Help → GeoStudio Help → Scripting API Reference
- **Video hướng dẫn**: "Getting Started with the GeoStudio Scripting API" (Seequent Community)
- **Webinar**: "Streamlining Geotechnical Workflows with API Scripting in GeoStudio 2025.2" (Bentley)
- **PyGeoStudio docs**: https://pygeostudio.readthedocs.io/en/stable/
- **PyGeoStudio GitHub**: https://github.com/MoiseRousseau/PyGeoStudio
- **Seequent Community**: https://community.seequent.com/discussion/2250/the-programming-capabilities-of-geostudio
- **GeoStudio 2025.1 Release Notes**: https://files.seequent.com/PDFs/GeoStudio-2025-1-ReleaseNotes-New-Features-Bug-Fixes-EN.pdf
- **GeoStudio 2025.2 Release Notes**: https://files.seequent.com/PDFs/GeoStudio-2025.2-Release-Notes-A4-EN-201125-V1.pdf
- **Seequent Help**: https://www.seequent.com/help-support/geostudio/
- **Seequent Developer Portal (Evo, không phải GeoStudio)**: https://developer.seequent.com/

---

## 8. Hướng dẫn cho Chat AI

### Khi người dùng yêu cầu tự động hóa GeoStudio:

1. **Ưu tiên PyGeoStudio** cho thao tác sửa file .gsz ngoài GeoStudio (đổi vật liệu, hình học, chạy tham số)
2. **Dùng GeoCmd** cho batch solve đơn giản
3. **Dùng GeoStudio Scripting API** khi người dùng làm việc bên trong GeoStudio 2025.1+
4. **Dùng đọc/ghi XML trực tiếp** khi cần kiểm soát hoàn toàn cấu trúc file, hoặc khi PyGeoStudio chưa hỗ trợ

### Nguyên tắc:
- Luôn kiểm tra phiên bản GeoStudio trước khi đề xuất phương thức
- PyGeoStudio **sửa** file có sẵn, không tạo mới từ đầu — cần file mẫu .gsz
- Kết quả SLOPE/W chưa đọc được qua PyGeoStudio → phải đọc CSV trong .gsz bằng `geoslope_inspect` hoặc XML trực tiếp
- Không đoán cú pháp API chính thức — tra Help trong GeoStudio hoặc hỏi người dùng
- Khi ghi XML trực tiếp, luôn dùng cấu trúc từ file mẫu đã kiểm chứng (GSIData version 11.x cho 2025.x)
