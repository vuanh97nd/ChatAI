"""PyGeoStudio inventory plus official gsi operations on project copies only."""
import json
import math
import shutil
import uuid
from pathlib import Path

from .files import digest


class GeoStudioPython:
    def __init__(self, files):
        self.files = files

    def prepare(self, name, args):
        path = self.files.path(args['path'])
        if path.suffix.lower() != '.gsz' or not path.is_file():
            raise ValueError('Cần dự án .gsz đã lưu trong whitelist.')
        operation = args.get('operation')
        if operation not in ('inspect', 'update_points', 'solve'):
            raise ValueError('operation: inspect, update_points hoặc solve.')
        analysis = args.get('analysis', '')
        if operation != 'inspect' and (not isinstance(analysis, str) or not analysis.strip()):
            raise ValueError('Cần tên analysis thật từ inspect.')
        updates = args.get('updates', '[]')
        updates = json.loads(updates) if isinstance(updates, str) else updates
        if not isinstance(updates, list) or len(updates) > 2000:
            raise ValueError('updates cần danh sách tối đa 2000 điểm.')
        if operation != 'update_points' and updates:
            raise ValueError('Chỉ update_points nhận updates.')
        seen = set()
        for row in updates:
            if not isinstance(row, dict) or type(row.get('index')) is not int or row['index'] < 1 or row['index'] in seen:
                raise ValueError('Mỗi điểm cần index 1-based duy nhất.')
            seen.add(row['index'])
            for key in ('before', 'after'):
                coords = row.get(key)
                if not isinstance(coords, list) or len(coords) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in coords):
                    raise ValueError('before/after phải là hai tọa độ hữu hạn, đơn vị mét.')
            if not isinstance(row.get('source'), str) or not row['source'].strip():
                raise ValueError('Cần nguồn tọa độ (DXF handle/vertex hoặc dữ kiện người dùng).')
        if operation == 'update_points' and not updates:
            raise ValueError('Chưa có tọa độ cần cập nhật.')
        output = self.files.path(str(path.parent / ('ChatAI-GeoStudio-' + uuid.uuid4().hex[:12] + '.gsz')), exists=False)
        return {'action': name, 'path': str(path), 'sha256': digest(path),
                'output': str(output), 'operation': operation, 'analysis': analysis,
                'updates': updates, 'note': 'Làm trên bản sao mới; không tạo vùng hoặc nhập DXF.'}

    def commit(self, plan):
        source = self.files.path(plan['path'])
        if digest(source) != plan['sha256']:
            raise ValueError('Dự án nguồn đã đổi; không dùng kế hoạch cũ.')
        output = self.files.path(plan['output'], exists=False)
        if output.exists():
            raise FileExistsError('Không ghi đè dự án.')
        # Inspect compatibility and ZIP/XML bounds before third-party parsing.
        from .geoslope_inspect import inspect_gsz
        saved = inspect_gsz(source)
        import PyGeoStudio as pgs
        import numpy as np
        model = pgs.GeoStudioFile(str(source))
        if plan['operation'] == 'inspect':
            return {'ok': True, 'path': str(source), 'inventory': saved,
                    'backend': 'PyGeoStudio', 'solved': False,
                    'note': 'Dữ liệu đã lưu; kết quả có sẵn không phải vừa tính.'}
        from .windows_apps import wait_automation, _STOP
        def check_stop():
            wait_automation()
            if _STOP.is_set():
                raise RuntimeError('Đã dừng. Không tự gửi lại thao tác trên bản sao.')
        check_stop()
        analysis = model.getAnalysisByName(plan['analysis'])
        if analysis is None:
            raise ValueError('Không tìm thấy analysis trong PyGeoStudio.')
        if analysis['Kind'] != 'SLOPE':
            raise ValueError('Tool này chỉ tính SLOPE/W, không đọc Fs từ analysis khác.')
        geometry = analysis['Geometry']
        points = np.asarray(geometry['Points'], dtype=float)
        if plan['operation'] == 'update_points':
            for row in plan['updates']:
                if row['index'] > len(points) or not np.allclose(points[row['index'] - 1], row['before'], rtol=0, atol=1e-7):
                    raise ValueError('Điểm/before không khớp dự án đã lưu; không sửa.')
                points = points.copy()
                points[row['index'] - 1] = row['after']
            from shapely.geometry import Polygon
            polygons = []
            for region in geometry['Regions'].values():
                polygon = Polygon([points[i - 1] for i in region[0]])
                if not polygon.is_valid or polygon.area <= 1e-10:
                    raise ValueError('Tọa độ mới làm vùng đất tự cắt hoặc mất diện tích.')
                if any(polygon.intersection(other).area > 1e-8 for other in polygons):
                    raise ValueError('Các vùng đất mới chồng lấn; không sửa.')
                polygons.append(polygon)
        import gsi
        from google.protobuf.json_format import MessageToDict
        shutil.copy2(source, output)
        project = None
        result = {'ok': False, 'output': str(output), 'source': str(source), 'solved': False}
        try:
            project = gsi.OpenProject(str(output))
            if plan['operation'] == 'update_points':
                # Read all targets before the first write; do not conflate XML IDs
                # with the official 1-based object array indices.
                def read_point(index):
                    response = project.Get(gsi.GetRequest(analysis=plan['analysis'],
                        object=f'CurrentAnalysis.GeometryItems.Points[{index}]'), timeout=30)
                    data = MessageToDict(response).get('data')
                    if isinstance(data, list) and len(data) == 1:
                        data = data[0]
                    if not isinstance(data, dict) or data.get('Units') != 'm' or not isinstance(data.get('Value'), list) or len(data['Value']) != 2:
                        raise ValueError('API point chưa có Value=[x,y], Units=m như ví dụ; không đoán kiểu.')
                    return data['Value']
                for row in plan['updates']:
                    if not np.allclose(read_point(row['index']), row['before'], rtol=0, atol=1e-7):
                        raise ValueError('API point khác PyGeoStudio/before; không sửa.')
                for row in plan['updates']:
                    check_stop()
                    request = gsi.SetRequest(analysis=plan['analysis'],
                        object=f'CurrentAnalysis.GeometryItems.Points[{row["index"]}]')
                    request.data.struct_value.update({'Value': row['after'], 'Units': 'm'})
                    project.Set(request, timeout=30)
                    if not np.allclose(read_point(row['index']), row['after'], rtol=0, atol=1e-7):
                        raise ValueError('Đọc lại tọa độ không khớp. Bản sao chưa xác minh; không gửi lại.')
                project.Save()
                result.update(ok=True, readback=plan['updates'], results_stale=True,
                              note='Đã xác minh tọa độ; phải kiểm tra nước/tải/miền trượt rồi tính lại.')
            else:
                check_stop()
                response = project.SolveAnalyses(gsi.SolveAnalysesRequest(analyses=[plan['analysis']]), timeout=3600)
                if not response.HasField('all_succeeded') or not response.all_succeeded:
                    raise RuntimeError('Solve không thành công: ' + str(MessageToDict(response)))
                check_stop()
                project.LoadResults(gsi.LoadResultsRequest(analysis=plan['analysis']), timeout=60)
                request = gsi.QueryResultsRequest(analysis=plan['analysis'], step=1,
                    table=gsi.ResultType.Slip,
                    dataparams=[gsi.DataParamType.eRawSlipFOS, gsi.DataParamType.eSlipNum])
                response = project.QueryResults(request, timeout=60)
                fs = list(response.results[gsi.DataParamType.eRawSlipFOS].values)
                ids = list(response.results[gsi.DataParamType.eSlipNum].values)
                if not fs or len(fs) != len(ids) or any(not math.isfinite(v) or v <= 0 for v in fs):
                    raise ValueError('Fs trống/không hợp lệ; không báo hoàn tất.')
                best = min(range(len(fs)), key=fs.__getitem__)
                project.Save()
                result.update(ok=True, solved=True, analysis=plan['analysis'],
                              safety_factor=fs[best], slip_number=ids[best], slip_count=len(fs))
        except Exception as error:
            result.update(ok=False, error=str(error),
                          note='Bản sao có thể đã sửa/tính một phần; không tự lặp thao tác. Nguồn giữ nguyên.')
        finally:
            if project is not None:
                project.Close()
        if digest(source) != plan['sha256']:
            raise RuntimeError('Nguồn đã thay đổi trong phiên; không xác nhận kết quả.')
        return result
