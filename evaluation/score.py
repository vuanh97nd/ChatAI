"""Chấm điểm do người đánh giá nhập; không tự gán điểm cho model."""
import argparse
import json
from pathlib import Path
DIMENSIONS=('accuracy','relevance','usefulness','grounding','clarity')

def summarize(path):
    rows=[json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    seen=set();totals=[]
    for row in rows:
        ident=row['id']
        if ident in seen or type(ident) is not int or not 1<=ident<=30:raise ValueError('ID sai/trùng.')
        seen.add(ident)
        values=[row[key] for key in DIMENSIONS]
        if any(type(value) not in (int,float) or not 0<=value<=4 for value in values):raise ValueError('Mỗi tiêu chí phải từ 0 đến 4.')
        totals.append(sum(values))
    return {'count':len(rows),'mean_out_of_20':round(sum(totals)/len(totals),2) if totals else None,'ids':sorted(seen)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('before');parser.add_argument('after',nargs='?')
    args=parser.parse_args();before=summarize(args.before)
    result={'before':before}
    if args.after:
        after=summarize(args.after);result['after']=after
        result['comparable']=before['ids']==after['ids'] and bool(before['count'])
        if result['comparable']:result['change']=round(after['mean_out_of_20']-before['mean_out_of_20'],2)
    print(json.dumps(result,ensure_ascii=False,indent=2))
