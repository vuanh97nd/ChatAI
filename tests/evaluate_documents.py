"""Live acceptance run. Run from project root; requires Ollama models and network."""
import argparse
import json
import re
from pathlib import Path
from assistant.document_intent import analyze_intent
from assistant.document_pipeline import prepare_events, document_instruction, response_text, document_footer
from assistant.prompts import SYSTEM


def main():
    import ollama
    parser=argparse.ArgumentParser();parser.add_argument('--model',default='qwen2.5:7b');parser.add_argument('--host',default='http://127.0.0.1:11434');parser.add_argument('--output',default='document-evaluation.json');args=parser.parse_args()
    client=ollama.Client(host=args.host);client.list() # fail clearly before reporting success
    cases=json.loads(Path('tests/document_cases.json').read_text());rows=[]
    for n,case in enumerate(cases,1):
        print(f'{n}/20: {case["question"]}',flush=True)
        messages=[{'role':'user','content':q} for q in case.get('history',[])]+[{'role':'user','content':case['question']}]
        intent=analyze_intent(client,messages,args.model)
        evidence=list(prepare_events(client,args.model,messages,use_web=True,intent=intent))[-1]['result']
        answer=response_text(client.chat(model=args.model,stream=False,messages=[{'role':'system','content':SYSTEM+document_instruction(evidence)},{'role':'user','content':case['question']}],options={'num_predict':1200}))
        footer=document_footer(evidence,answer)
        rows.append({'case':case,'intent':intent,'queries':(evidence.get('web_results') or {}).get('queries',[]),'evidence':evidence,'answer':answer+footer,
            'automatic_checks':{'at_most_one_question':answer.count('?')<=1,
             'clean_queries':not any(re.match(r'^(tóm tắt|tìm |giải thích|phân tích|so sánh|trích |dịch )',q,re.I) for q in (evidence.get('web_results') or {}).get('queries',[])),
             'all_summaries_map_complete':all(d.get('processed_full',False) for d in evidence['documents'])},
            'human_review_required':['Không bịa nghĩa/mã/điều khoản/số liệu','Nguồn dẫn thực sự hỗ trợ từng ý','Không hỏi thừa','Đúng tài liệu và mức độ bao phủ','Tài liệu không tồn tại được xử lý trung thực']})
    Path(args.output).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Đã lưu kết quả; cần duyệt các tiêu chí ngữ nghĩa trước khi kết luận đạt.')

if __name__=='__main__':main()
