"""Permission-gated PDF page reading through the configured account API."""
from .documents import pdf_vision_ocr


def online_pdf_reader(cfg, session, *, cancel_event=None, on_status=None, client_factory=None):
    if not (cfg.get('online_tools_enabled') is True and cfg.get('online_document_upload') is True):
        if on_status:
            missing=[]
            if cfg.get('online_tools_enabled') is not True:missing.append('công cụ API trực tuyến chưa bật')
            if cfg.get('online_document_upload') is not True:missing.append('quyền gửi ảnh trang tài liệu chưa bật')
            on_status('AI đọc ảnh PDF chưa được chọn: '+', '.join(missing)+'. Số trang tối đa không tự bật các quyền này.')
        return None
    if not session:
        raise ValueError('Đăng nhập trước khi dùng công cụ đọc PDF trực tuyến.')
    # Any configured online AI that reads images may OCR PDF pages, not only DeepSeek Flash.
    provider=cfg.get('online_document_provider') or 'deepseek_flash'
    from .cloud import ServerApiClient
    client=(client_factory or ServerApiClient)(session,provider,cancel_event=cancel_event,on_status=on_status,retry_limit=0)
    class VisionAdapter:
        def chat(self, *, messages, **kwargs):
            converted=[]
            for message in messages:
                item=dict(message)
                images=item.pop('images',[])
                if images:
                    item['content']=[{'type':'text','text':item['content']}]+[
                        {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+x}} for x in images]
                converted.append(item)
            return client.chat(model='document',messages=converted,options={'num_predict':4096,'temperature':0})
    read=pdf_vision_ocr(VisionAdapter(),provider)
    cache={};counts={}
    limit=0  # every page is read; no page cap (user request)
    def page(raw,index):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('Đã dừng đọc PDF trực tuyến.')
        page.skip_reason=''
        key=(raw,index)
        if key in cache:return cache[key]
        count=counts.get(raw,0)
        if limit>0 and count>=limit:
            page.skip_reason=f'Đã chạm giới hạn đọc ảnh PDF {limit} trang của tệp; tăng Số trang nhận dạng tối đa trong Công cụ trực tuyến để đọc tiếp. Trang này chưa được gửi OCR.'
            return ''
        counts[raw]=count+1
        if on_status:on_status(f'Đang đọc trang {index+1} qua {provider}; '+(f'tối đa {limit} trang.' if limit else 'không giới hạn số trang.'))
        cache[key]=read(raw,index)
        return cache[key]
    page.on_status=on_status
    page.max_pages=limit
    page.skip_reason=''
    page.source='API trực tuyến '+provider
    return page
