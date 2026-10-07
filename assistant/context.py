"""Giới hạn dữ liệu tham khảo bằng cấu trúc JSON hợp lệ, không cắt JSON giữa chuỗi."""
import json
from copy import deepcopy


def compact_evidence(state,memories=(),budget=4000):
    result={}
    if state.get("memory_write_status"):result["memory_write_status"]=state["memory_write_status"]
    prepared=state.get('prepared_documents',[])
    if prepared:
        result['prepared_documents']=deepcopy(prepared)
    if state.get('document_intent'):
        result['intent']=deepcopy(state['document_intent'])
    if state.get('document_errors'):result['document_errors']=state['document_errors'][:3]
    web=state.get('web_results')
    if web and not prepared:
        result['web']={'note':web.get('note',''),'errors':web.get('errors',[])[:2],
            'sources':[{'id':s.get('id',''),'title':s.get('title','')[:120],'url':s.get('url','')[:500],
                'read':s.get('read',False),'snippet':s.get('snippet','')[:200]}
                for s in web.get('sources',[])[:5]],
            'pages':[{'id':s.get('id',''),'title':s.get('title','')[:100],'url':s.get('url','')[:500],
                'text':s.get('text','')[:1800],'truncated':True,'full_text':False}
                for s in web.get('pages',[])[:3]]}
    if state.get('rag_results') and not prepared:
        result['documents']={'note':state['rag_results'].get('note',''),
            'sources':[{'source':s['source'],'chunk':s['chunk'],'text':s['text'][:800]}
                for s in state['rag_results'].get('sources',[])[:4]]}
    if state.get('attached_documents') and not prepared:
        result['attachments']=[{k:deepcopy(v) for k,v in item.items() if k!='units'} for item in state['attached_documents']]
    if memories:result['memory']=deepcopy(list(memories)[:4])
    def encode():return json.dumps(result,ensure_ascii=False)
    # Rút text, vẫn giữ nhãn và nguồn; không sửa dữ liệu đã lưu trong SQLite.
    while len(encode())>budget:
        candidates=[]
        def collect(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if isinstance(item,str) and key not in ('url','source','title','id') and len(item)>120:
                        candidates.append((value,key,item))
                    elif isinstance(item,(dict,list)):collect(item)
            elif isinstance(value,list):
                for item in value:collect(item)
        collect(result)
        if not candidates:break
        parent,key,text=max(candidates,key=lambda item:len(item[2]))
        parent[key]=text[:max(100,len(text)//2)]+' [đã rút gọn]'
        if key in ('text','summary','quote'):parent['context_truncated']=True;parent['truncated']=True
    # Attachment dict đã sao chép trước khi rút để không đổi snapshot gốc.
    result['context_note']='prepared_documents là kết quả xử lý các phần chữ; phân biệt full_text/processed_full với context_truncated. Snippet/chunk riêng không chứng minh toàn văn.'
    return result
