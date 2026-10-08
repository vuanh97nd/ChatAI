"""Permission-gated PDF page reading through the configured account API."""
from .documents import pdf_vision_ocr


def online_pdf_reader(cfg, session, *, cancel_event=None, on_status=None, client_factory=None):
    if not (cfg.get('online_tools_enabled') is True and cfg.get('online_document_upload') is True):
        return None
    if not session:
        raise ValueError('Đăng nhập trước khi dùng công cụ đọc PDF trực tuyến.')
    provider=cfg.get('online_document_provider','deepseek_flash')
    if provider not in ('deepseek_flash','gemini','nvidia'):
        raise ValueError('Chọn DeepSeek Flash, Gemini hoặc NVIDIA Vision để đọc trang PDF.')
    from .cloud import ServerApiClient
    client=(client_factory or ServerApiClient)(session,provider,cancel_event=cancel_event,on_status=on_status,retry_limit=0)
    class VisionAdapter:
        def chat(self, *, messages, **kwargs):
            converted=[]
            for message in messages:
                item=dict(message)
                images=item.pop('images',[])
                if images:
                    if any(len(x)>1398104 for x in images):
                        raise ValueError('Ảnh trang vượt giới hạn API 1 MiB; không gửi.')
                    item['content']=[{'type':'text','text':item['content']}]+[
                        {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+x}} for x in images]
                converted.append(item)
            return client.chat(model='document',messages=converted,options={'num_predict':4096,'temperature':0})
    read=pdf_vision_ocr(VisionAdapter(),provider)
    cache={};counts={}
    limit=cfg.get('online_document_pages',40)
    def page(raw,index):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('Đã dừng đọc PDF trực tuyến.')
        page.skip_reason=''
        key=(raw,index)
        if key in cache:return cache[key]
        count=counts.get(raw,0)
        if count>=limit:
            page.skip_reason=f'Đã chạm giới hạn đọc ảnh PDF {limit} trang của tệp; tăng Số trang nhận dạng tối đa trong Công cụ trực tuyến để đọc tiếp. Trang này chưa được gửi OCR.'
            return ''
        counts[raw]=count+1
        if on_status:on_status(f'Đang đọc trang {index+1} qua {provider}; tối đa {limit} trang cần nhận dạng.')
        cache[key]=read(raw,index)
        return cache[key]
    page.on_status=on_status
    page.max_pages=limit
    page.skip_reason=''
    page.source='API trực tuyến '+provider
    return page
