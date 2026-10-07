"""Sequential specialist handoffs using observed tool artifacts, scoped to one chat."""
import hashlib
import json
import re
from pathlib import Path
from .modules import CHAT_MODELS


def collaboration_intent(question, category='', mode=0):
    text=question.casefold()
    code=category=='coding' or bool(re.search(r'\b(code|python|javascript|typescript|html|css|website|web app|lập trình|mã nguồn)\b',text))
    media=None
    if code:
        negative=bool(re.search(r'(không|đừng|chưa)\s+(cần\s+)?(tạo|vẽ|sinh)|đề xuất|ý tưởng|trao đổi|nói trước',text))
        if not negative:
            if mode==3 or re.search(r'(tạo|sinh|generate|create)\s+(một\s+|1\s+)?(video|clip)',text):media='video_generate'
            elif mode==2 or re.search(r'(tạo|vẽ|sinh|generate|create)\s+(một\s+|1\s+)?(ảnh|hình ảnh|hình|image|logo)',text):media='image_generate'
    return {'enabled':code,'media_tool':media,'stage':'media' if media else 'code',
            'active_model':None,'notice_sent':False,'media_retries':0,'artifacts':[], 'media_status':None}


def collect_artifacts(result, roots, producer):
    """Accept only real local outputs from a successful tool, never model prose."""
    if result.get('ok') is not True:return []
    roots=[Path(r).resolve() for r in roots];items=[]
    raw_paths=[('image',p) for p in result.get('images',[])[:8] if isinstance(p,str)]
    if isinstance(result.get('video'),str):raw_paths.append(('video',result['video']))
    _DOC_EXTS={'.gsz','.dxf','.docx','.xlsx','.pdf','.csv','.txt','.py','.json','.xml','.zip'}
    for raw in result.get('files',[])[:10]:
        if isinstance(raw,str):
            suffix=Path(raw).suffix.lower()
            kind='video' if suffix=='.mp4' else 'file' if suffix in _DOC_EXTS else 'image'
            raw_paths.append((kind,raw))
    for raw in result.get('artifacts',[])[:10]:
        if isinstance(raw,str):
            suffix=Path(raw).suffix.lower()
            kind='video' if suffix=='.mp4' else 'file' if suffix in _DOC_EXTS else 'image'
            raw_paths.append((kind,raw))
    for kind,raw in raw_paths:
        try:
            path=Path(raw).resolve(strict=True)
            if not path.is_file() or not any(path.is_relative_to(r) for r in roots):continue
            if kind not in ('file',) and path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.mp4'):continue
            size=path.stat().st_size
            if not 0<size<=512*1024**2:continue
            sha=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):sha.update(chunk)
            expected=next((a for a in result.get('artifact_manifest',[]) if a.get('path')==str(path)),None)
            if expected and expected.get('sha256')!=sha.hexdigest():continue
            item={'kind':kind,'path':str(path),'filename':path.name,'bytes':size,
                  'sha256':sha.hexdigest(),'producer':producer,'status':'created'}
            if kind=='file':
                items.append(item);continue
            if kind=='image':
                from PIL import Image
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:item.update(width=image.width,height=image.height,format=image.format)
            elif isinstance(result.get('duration_seconds'),(int,float)):
                item['reported_duration_seconds']=result['duration_seconds']
            items.append(item)
        except Exception:continue
    return items


def existing_artifacts(state, roots):
    """Latest successful media tool result in this conversation; no cross-account retrieval."""
    for msg in reversed(state.get('messages',[])):
        if msg.get('role')!='tool' or msg.get('tool_name') not in ('image_generate','video_generate','image_resize','video_from_images','python_run'):continue
        try:result=json.loads(msg['content'])
        except (ValueError,KeyError,TypeError):continue
        artifacts=collect_artifacts(result,roots,msg['tool_name'])
        if artifacts:return artifacts
    return []


def choose_coder(client, requested, current):
    if requested==current or 'coder' in current or current.split(':')[0]=='codestral':return current,None
    if requested not in CHAT_MODELS:return current,'AI lập trình đã cấu hình không có trong danh mục; dùng AI hiện tại.'
    try:
        names={m.model for m in client.list().models}
        names |= {name.removesuffix(':latest') for name in names}
        if requested in names:return requested,None
    except Exception:
        return current,'Chưa kiểm tra được AI lập trình; dùng AI hiện tại và không tự tải AI mới.'
    return current,'Chưa tải '+requested+'; dùng AI hiện tại. Có thể tải AI lập trình trong mục Tải mô hình.'


def handoff_instruction(plan):
    if not plan.get('enabled'):return ''
    if plan['stage']=='vision':
        return ('\nPHỐI HỢP: Đọc ảnh đính kèm và tạo bản mô tả ngắn cho AI lập trình: bố cục, màu, chữ nhìn rõ và yêu cầu triển khai. '
                'Không viết code; không đoán chữ mờ, tên file, đường dẫn hoặc nội dung ảnh không quan sát được. Bản mô tả này chưa được kiểm chứng độc lập.')
    if plan['stage']=='media':
        return ('\nPHỐI HỢP: Người dùng cần tạo tài nguyên rồi viết code sử dụng tài nguyên. '
                'Trước hết gọi '+plan['media_tool']+' với mô tả phù hợp và chờ xác nhận. '
                'Chưa viết code hoặc nhận ảnh đã tạo trước khi có kết quả công cụ thành công. Không dùng web khi nút tìm kiếm tắt.')
    return '\nDỮ LIỆU BÀN GIAO: '+json.dumps({'media_status':plan.get('media_status'),
        'artifacts':plan.get('artifacts',[]),'vision_brief':plan.get('vision_brief','')},ensure_ascii=False)



def refresh_artifacts(plan, roots):
    old=plan.get('artifacts',[])
    if not old:return False
    result={'ok':True,'images':[a['path'] for a in old if a.get('kind')=='image'],
            'artifact_manifest':old}
    video=next((a['path'] for a in old if a.get('kind')=='video'),None)
    if video:result['video']=video
    checked=collect_artifacts(result,roots,'verified_handoff')
    previous={a['path']:a for a in old}
    for item in checked:item['producer']=previous[item['path']]['producer']
    changed=len(checked)!=len(old)
    plan['artifacts']=checked
    if changed:plan['media_status']='changed_or_missing'
    return changed
