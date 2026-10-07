"""Python tính toán với AST giới hạn; không eval/exec, không IO.

Bản 2026-10-06: chấp nhận cách viết tự nhiên của model nhỏ (15%, 1.200.000, 2,5,
x, ^, °F, "độ C", "mét"...) và tên phép tính gần đúng, để giảm lỗi gọi công cụ.
"""
import ast
import re
from decimal import Decimal, localcontext, ROUND_FLOOR
from datetime import date, datetime
from zoneinfo import ZoneInfo

CALCULATOR_SCHEMA = {'type':'function','function':{'name':'calculate',
    'description':('Tính chính xác bằng Python. LUÔN dùng công cụ này cho mọi phép tính, đổi đơn vị, thống kê, số ngày. '
                   'operation="expression": expression là biểu thức số, ví dụ "0.1+0.2", "1200000*(1-15/100)", "sqrt(2)". '
                   'operation="convert": value, from_unit, to_unit; ví dụ value=32, from_unit="F", to_unit="C"; value=2.5, from_unit="km", to_unit="m". '
                   'operation="statistics": values là danh sách số, trả mean/median/sum/min/max. '
                   'operation="date_difference": start, end dạng YYYY-MM-DD. operation="now": giờ hiện tại theo timezone.'),
    'parameters':{'type':'object','properties':{
        'operation':{'type':'string','enum':['expression','statistics','convert','date_difference','now']},
        'expression':{'type':'string'},'values':{'type':'array','items':{'type':'number'},'maxItems':1000},
        'value':{'type':'number'},'from_unit':{'type':'string'},'to_unit':{'type':'string'},
        'start':{'type':'string'},'end':{'type':'string'},'timezone':{'type':'string'}},
        'required':['operation'],'additionalProperties':False}}}

# (đại lượng, hệ số về đơn vị gốc)
UNITS = {'mm':('length','0.001'),'cm':('length','0.01'),'dm':('length','0.1'),'m':('length','1'),
    'km':('length','1000'),'in':('length','0.0254'),'ft':('length','0.3048'),'yd':('length','0.9144'),
    'mi':('length','1609.344'),'nmi':('length','1852'),
    'mg':('mass','0.000001'),'g':('mass','0.001'),'kg':('mass','1'),'t':('mass','1000'),
    'lb':('mass','0.45359237'),'oz':('mass','0.028349523125'),
    's':('time','1'),'min':('time','60'),'h':('time','3600'),'day':('time','86400'),'week':('time','604800'),
    'ml':('volume','0.001'),'l':('volume','1'),'m3':('volume','1000'),
    'mm2':('area','0.000001'),'cm2':('area','0.0001'),'m2':('area','1'),'ha':('area','10000'),'km2':('area','1000000'),
    'm/s':('speed','1'),'km/h':('speed','0.27777777777777777777777777777777777778'),
    'pa':('pressure','1'),'kpa':('pressure','1000'),'mpa':('pressure','1000000'),'bar':('pressure','100000'),'atm':('pressure','101325'),
    'w':('power','1'),'kw':('power','1000'),'mw':('power','1000000'),'hp':('power','745.69987158227022'),
    'j':('energy','1'),'kj':('energy','1000'),'wh':('energy','3600'),'kwh':('energy','3600000'),'cal':('energy','4.184'),'kcal':('energy','4184')}

UNIT_ALIASES = {
    'mét':'m','met':'m','meter':'m','metre':'m','meters':'m','mét vuông':'m2','m²':'m2','m^2':'m2','m³':'m3','m^3':'m3','khối':'m3',
    'kilomet':'km','kilômét':'km','ki-lô-mét':'km','kilometer':'km','kilometre':'km','cây số':'km',
    'centimet':'cm','xăng-ti-mét':'cm','xentimet':'cm','milimet':'mm','mi-li-mét':'mm','inch':'in','foot':'ft','feet':'ft',
    'mile':'mi','miles':'mi','dặm':'mi','hải lý':'nmi','km²':'km2','hecta':'ha','héc-ta':'ha','hectare':'ha',
    'gram':'g','gam':'g','kilogram':'kg','kilôgam':'kg','cân':'kg','tấn':'t','ton':'t','tonne':'t','pound':'lb','lbs':'lb','ounce':'oz',
    'giây':'s','sec':'s','second':'s','seconds':'s','phút':'min','minute':'min','minutes':'min','giờ':'h','tiếng':'h','hour':'h','hours':'h',
    'ngày':'day','days':'day','d':'day','tuần':'week','weeks':'week',
    'lít':'l','lit':'l','liter':'l','litre':'l','mililit':'ml','mililít':'ml',
    'kmh':'km/h','km/giờ':'km/h','kph':'km/h','mps':'m/s','m/giây':'m/s',
    'oát':'w','watt':'w','kilowatt':'kw','mã lực':'hp','số điện':'kwh','kw.h':'kwh','kw·h':'kwh','calo':'cal','kcalo':'kcal',
}
TEMP_ALIASES = {'c':'c','°c':'c','ºc':'c','độ c':'c','celsius':'c','độ':'c',
                'f':'f','°f':'f','ºf':'f','độ f':'f','fahrenheit':'f',
                'k':'k','kelvin':'k','độ k':'k'}

OPERATION_ALIASES = {
    'expression':'expression','calculate':'expression','calculation':'expression','arithmetic':'expression','math':'expression',
    'compute':'expression','eval':'expression','add':'expression','subtract':'expression','multiply':'expression','divide':'expression',
    'percent':'expression','percentage':'expression','discount':'expression','formula':'expression',
    'statistics':'statistics','stats':'statistics','statistic':'statistics','mean':'statistics','average':'statistics','median':'statistics',
    'convert':'convert','conversion':'convert','unit_conversion':'convert','convert_unit':'convert','unit':'convert','units':'convert',
    'date_difference':'date_difference','date_diff':'date_difference','days_between':'date_difference','datediff':'date_difference','days':'date_difference',
    'now':'now','time':'now','current_time':'now','datetime':'now',
}


def plain(value):
    """Decimal -> chuỗi dễ đọc, không mũ khoa học, bỏ số 0 thừa."""
    if not isinstance(value, Decimal):return str(value)
    text=format(value.normalize(),'f')
    if '.' in text:text=text.rstrip('0').rstrip('.')
    return '0' if text in ('-0','') else text


def number(value):
    if isinstance(value,bool):raise ValueError('Không nhận boolean làm số.')
    if isinstance(value,str):value=normalize_expression(value)
    result=Decimal(str(value))
    if not result.is_finite() or abs(result)>Decimal('1e100'):
        raise ValueError('Số không hữu hạn hoặc vượt giới hạn 1e100.')
    return result


def normalize_expression(text):
    """Chuẩn hóa cách viết số kiểu Việt Nam và ký hiệu thông dụng sang cú pháp Python."""
    expr=str(text).strip()
    expr=re.sub(r'(?i)(đồng|vnđ|vnd|đ)\b','',expr)
    expr=expr.replace('×','*').replace('·','*').replace('÷','/').replace('−','-').replace('^','**').replace('√','sqrt')
    expr=re.sub(r'(?<=\d)\s*[xX]\s*(?=\d)','*',expr)
    expr=expr.rstrip('= ').strip()
    # Nghìn kiểu VN: 1.200.000 -> 1200000 (ít nhất hai nhóm 3 chữ số)
    expr=re.sub(r'(?<![\d.,])\d{1,3}(?:\.\d{3}){2,}(?![\d.,]*\d)',lambda m:m.group(0).replace('.',''),expr)
    # Nghìn kiểu Anh: 1,200,000 -> 1200000
    expr=re.sub(r'(?<![\d.,])\d{1,3}(?:,\d{3}){2,}(?![\d,]*\d)',lambda m:m.group(0).replace(',',''),expr)
    # Thập phân dấu phẩy: 2,5 -> 2.5
    expr=re.sub(r'(?<=\d),(?=\d)','.',expr)
    # Phần trăm: 15% -> (15/100); giữ % là modulo khi phía sau là số/ngoặc
    expr=re.sub(r'(\d+(?:\.\d+)?)\s*%(?!\s*[\d(])',r'(\1/100)',expr)
    return expr


def expression_value(expression):
    if not isinstance(expression,str) or len(expression)>500:raise ValueError('Biểu thức tối đa 500 ký tự.')
    source=normalize_expression(expression)
    try:tree=ast.parse(source,mode='eval')
    except SyntaxError:raise ValueError(f'Biểu thức không hợp lệ: "{expression}". Chỉ dùng số và + - * / ** ( ), ví dụ "1200000*(1-15/100)".')
    if sum(1 for _ in ast.walk(tree))>100:raise ValueError('Biểu thức quá phức tạp.')
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            return number(ast.get_source_segment(source,node))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand);return value if isinstance(node.op,ast.UAdd) else -value
        if isinstance(node,ast.BinOp):
            left,right=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add):value=left+right
            elif isinstance(node.op,ast.Sub):value=left-right
            elif isinstance(node.op,ast.Mult):value=left*right
            elif isinstance(node.op,ast.Div):
                if right==0:raise ValueError('Chia cho 0.')
                value=left/right
            elif isinstance(node.op,ast.FloorDiv):value=(left/right).to_integral_value(rounding=ROUND_FLOOR)
            elif isinstance(node.op,ast.Mod):value=left-(left/right).to_integral_value(rounding=ROUND_FLOOR)*right
            elif isinstance(node.op,ast.Pow):
                if right!=right.to_integral_value() or abs(right)>100:raise ValueError('Số mũ phải nguyên, trị tuyệt đối <=100.')
                value=left**int(right)
            else:raise ValueError('Toán tử không hỗ trợ.')
            return number(value)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and len(node.args)==1 and not node.keywords:
            value=visit(node.args[0])
            if node.func.id=='sqrt':return value.sqrt()
            if node.func.id=='abs':return abs(value)
            if node.func.id=='round':return value.quantize(Decimal(1))
        raise ValueError('Chỉ nhận biểu thức số; không nhận code, biến, import, thuộc tính hoặc truy cập file.')
    with localcontext() as context:
        context.prec=40
        return visit(tree.body)


def _unit(name):
    key=str(name or '').strip().lower()
    key=re.sub(r'\s+',' ',key)
    if key in TEMP_ALIASES:return 'temp',TEMP_ALIASES[key]
    key=UNIT_ALIASES.get(key,key)
    if key in UNITS:return UNITS[key][0],key
    raise ValueError(f'Đơn vị chưa hỗ trợ: "{name}". Dùng ký hiệu như m, km, kg, h, l, m2, C, F, K.')


def _to_kelvin(value,unit):
    if unit=='c':return value+Decimal('273.15')
    if unit=='f':return (value-32)*5/9+Decimal('273.15')
    return value


def _from_kelvin(value,unit):
    if unit=='c':return value-Decimal('273.15')
    if unit=='f':return (value-Decimal('273.15'))*9/5+32
    return value


def _date(text):
    text=str(text).strip()
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y'):
        try:return datetime.strptime(text,fmt).date()
        except ValueError:pass
    raise ValueError(f'Ngày không hợp lệ: "{text}". Dùng dạng YYYY-MM-DD.')


def calculate(operation, **args):
    op=OPERATION_ALIASES.get(str(operation or '').strip().lower())
    if op is None:
        # Model gọi tên phép tính lạ nhưng có biểu thức: vẫn tính được.
        if args.get('expression'):op='expression'
        elif args.get('values'):op='statistics'
        elif args.get('from_unit') and args.get('to_unit'):op='convert'
        elif args.get('start') and args.get('end'):op='date_difference'
        else:raise ValueError('operation phải là expression, statistics, convert, date_difference hoặc now.')
    with localcontext() as context:
        context.prec=40
        if op=='expression':
            if not args.get('expression'):raise ValueError('Thiếu expression, ví dụ "0.1+0.2".')
            value=expression_value(args['expression'])
            return {'ok':True,'result':plain(value),'expression':args['expression'],'precision_digits':40}
        if op=='statistics':
            values=args.get('values',[])
            if not isinstance(values,list) or not 1<=len(values)<=1000:raise ValueError('Cần 1–1000 giá trị.')
            values=sorted(number(v) for v in values);n=len(values);total=sum(values,Decimal(0))
            median=values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2
            return {'ok':True,'count':n,'sum':plain(total),'mean':plain(total/n),'median':plain(median),'min':plain(values[0]),'max':plain(values[-1])}
        if op=='convert':
            if 'value' not in args:raise ValueError('Thiếu value cần đổi.')
            value=number(args['value'])
            (kind_a,source),(kind_b,target)=_unit(args.get('from_unit')),_unit(args.get('to_unit'))
            if kind_a!=kind_b:raise ValueError(f'Không đổi được {args.get("from_unit")} sang {args.get("to_unit")} vì khác đại lượng.')
            if kind_a=='temp':result=_from_kelvin(_to_kelvin(value,source),target)
            else:result=value*Decimal(UNITS[source][1])/Decimal(UNITS[target][1])
            label={'c':'°C','f':'°F','k':'K'}.get(target,target)
            return {'ok':True,'result':plain(result),'unit':label,'input':f'{plain(value)} {args.get("from_unit")}'}
        if op=='date_difference':
            days=(_date(args['end'])-_date(args['start'])).days
            return {'ok':True,'days':days,'note':'Không cộng thêm ngày đầu; end - start.'}
        if op=='now':
            timezone=args.get('timezone') or 'Asia/Ho_Chi_Minh'
            return {'ok':True,'datetime':datetime.now(ZoneInfo(timezone)).isoformat(),'timezone':timezone}
    raise ValueError('Phép tính không hỗ trợ.')
