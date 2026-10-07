"""Chạy bộ câu hỏi thật trên Ollama; báo kiểm tra cơ học, chấm nội dung bằng người.
Ví dụ: runtime/python/python.exe run_document_benchmark.py --case 5 --web
Không bật --web thì mọi câu chạy với quyền web tắt. Không có thao tác ghi file người dùng.
"""
import argparse
import contextlib
import io
import json
import re
import tempfile
from pathlib import Path
from datetime import datetime
from assistant.agent import Agent
from assistant.config import load_config,ROOT
from assistant.storage import Store
from assistant.documents import read_local


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',type=int,help='ID 1..20; mặc định tất cả')
    parser.add_argument('--web',action='store_true',help='Mô phỏng người dùng bật nút Tìm kiếm mạng')
    parser.add_argument('--attachment',type=Path,help='File tự cung cấp cho case đính kèm')
    args=parser.parse_args()
    import ollama
    cfg=load_config();client=ollama.Client(host=cfg['ollama_host'],timeout=cfg.get('timeout_seconds',180))
    cases=json.loads((ROOT/'tests/document_cases.json').read_text(encoding='utf-8'))
    if args.case:cases=[c for c in cases if c['id']==args.case]
    output=[]
    with tempfile.TemporaryDirectory(prefix='chatai-benchmark-') as temporary:
        store=Store(Path(temporary)/'history.sqlite3')
        for case in cases:
            if case.get('attached') and not args.attachment:
                output.append({'id':case['id'],'skipped':'Cần --attachment file mẫu phù hợp.'});continue
            cid=store.create();state=store.load(cid)
            state['messages']=[{'role':'user','content':q} for q in case.get('history',[])]
            store.save(cid,state)
            agent=Agent(client,None,cfg,store,cid,tools_enabled=False)
            agent.start(state,case['question'],cfg['default_model'])
            state.update(ui_mode=4 if args.web else 0,web_search_requested=args.web)
            if case.get('attached'):state['attached_documents']=[read_local(args.attachment)]
            print('Case',case['id'],case['question'],flush=True)
            for event in agent.run(state):
                if event['type']=='status':print(' ',event['text'],flush=True)
            answer=next((m.get('content','') for m in reversed(state['messages']) if m['role']=='assistant'),'')
            query_list=(state.get('web_results') or {}).get('queries',[])
            output.append({'id':case['id'],'question':case['question'],'answer':answer,
                'intent':state.get('document_intent'),'queries':query_list,
                'source_coverage':[{k:d.get(k) for k in ('id','file','url','processed_full','parts_total','parts_processed','failed_parts')}
                    for d in state.get('prepared_documents',[])],
                'automatic_checks':{'clean_query':not any(re.search(r'^(hãy|tóm tắt|giải thích|tìm nguồn|dịch)\b',q,re.I) for q in query_list),
                    'no_web_when_off':args.web or not state.get('web_results'),
                    'no_fixed_partial_footer':'(đã đọc phần nội dung bị cắt)' not in answer},
                'manual_scores':{'understands_need':None,'no_fabrication':None,'supported_sources':None,'fulltext_summary':None,'natural_helpful':None},
                'criteria':case['checks']})
    path=ROOT/'data'/('document-benchmark-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Đã lưu:',path)

if __name__=='__main__':main()
