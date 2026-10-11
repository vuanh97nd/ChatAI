"""Live coordinate planning for flat-ground rectangular PLAXIS 2D excavations."""
import json
import math
from .plaxis_stage_guard import StageGuardError, value


def excavation_plan(g, raw):
    try: spec=json.loads(raw)
    except (TypeError, ValueError):raise StageGuardError('plan_excavation cần JSON x_left, width, depth, source.') from None
    if not isinstance(spec,dict) or set(spec)!={'x_left','width','depth','source'}:
        raise StageGuardError('Cần x_left, width, depth, source; không tự đặt cao độ mặt đất.')
    if any(type(spec[k]) not in (int,float) or not math.isfinite(spec[k]) for k in ('x_left','width','depth')):
        raise StageGuardError('Kích thước phải là số hữu hạn.')
    if spec['width']<=0 or spec['depth']<=0 or not isinstance(spec['source'],str) or not spec['source'].strip():
        raise StageGuardError('Chiều rộng/chiều sâu phải dương và có nguồn đề bài/manual.')
    try:
        boreholes=list(g.Boreholes)
        if not boreholes:raise ValueError('Chưa có borehole')
        tops=[float(value(g.getsoillayerlevel(b,0))) for b in boreholes]
        bottoms=[float(value(g.getsoillayerlevel(b,len(g.Soillayers)))) for b in boreholes]
        box=g.SoilContour.BoundingBox
        xmin,xmax,ymin,ymax=[float(value(getattr(box,k))) for k in ('xMin','xMax','yMin','yMax')]
    except Exception as exc:raise StageGuardError('Chưa đọc được cao độ đất và biên SoilContour; đọc trong chế độ soil trước: '+str(exc)[:150]) from None
    if not all(math.isfinite(n) for n in tops+bottoms+[xmin,xmax,ymin,ymax]):
        raise StageGuardError('Cao độ/biên mô hình không hữu hạn.')
    if any(abs(t-tops[0])>1e-6 for t in tops):
        raise StageGuardError('Mặt đất không phẳng; cần hình học theo từng borehole, không dùng kế hoạch hình chữ nhật.')
    x0=spec['x_left'];x1=x0+spec['width'];top=tops[0];bottom=top-spec['depth']
    if not xmin<=x0<x1<=xmax or not max(ymin,max(bottoms))<=bottom<top<=ymax:
        raise StageGuardError('Vùng đào nằm ngoài miền đất hiện tại; kiểm tra đơn vị, mốc cao độ và kích thước manual.')
    return {'points':[[x0,bottom],[x1,bottom],[x1,top],[x0,top]],
            'ground_level':top,'bottom_level':bottom,'source':spec['source'],
            'region':{'x':[x0,x1],'y':[bottom,top]},
            'note':'Kế hoạch 2D mặt đất phẳng, kích thước theo đơn vị dự án. Chưa vẽ/chưa đổi Active.'}


def read_points(g, expected):
    observed=[]
    try:
        for p in g.Points:
            observed.append([float(value(p.x)),float(value(p.y))])
    except Exception as exc:raise StageGuardError('Polygon đã gửi; chưa đọc lại được điểm, không tạo lại: '+str(exc)[:150]) from None
    if not all(any(all(abs(a-b)<=1e-6 for a,b in zip(point,want)) for point in observed) for want in expected):
        raise StageGuardError('Polygon đã gửi nhưng chưa xác minh đủ tọa độ đỉnh; đọc model_state, không vẽ lại.')
    return {'point_coordinates_verified':True,'expected_points':expected,
            'note':'Đã tìm thấy các tọa độ trong g.Points; chưa chứng minh liên kết polygon hoặc đúng vùng đất/phase. Cần inspect_stage/verify_stage trước khi đào.'}


GEOMETRY_INSTRUCTION=(
    '\nĐào chữ nhật PLAXIS 2D trên mặt đất phẳng: dùng plan_excavation args [JSON hoặc object '
    'với x_left,width,depth,source lấy từ đề bài/manual]. Công cụ đọc cao độ borehole và biên SoilContour '
    'hiện tại; đáy=mặt đất-depth, không mặc định y=0. Đọc kế hoạch rồi dùng draw_excavation với cùng '
    'tham số trong chế độ soil/structures; công cụ đọc lại mốc trước khi gửi polygon và kiểm tra điểm '
    'sau vẽ. Không dùng polygon trực tiếp để bỏ qua bước lập kế hoạch đào. Các điểm tồn tại không '
    'chứng minh vùng đất/phase đúng: inspect_stage và verify_stage vẫn bắt buộc trước đổi Active. '
    'Mặt đất dốc, 3D hoặc hình không chữ nhật: đọc hình học/manual và xác minh từng đỉnh bằng '
    'verify_model; không áp dụng kế hoạch 2D này. Thiếu vị trí/kích thước/đơn vị thì hỏi phần thiếu.'
)
