"""Đo điểm gốc (baseline) Chat AI trên bộ 30 câu evaluation/questions.json.

Chạy từ thư mục Chat-AI:
    runtime\\python\\python.exe evaluation\\run_baseline.py --label before
    runtime\\python\\python.exe evaluation\\run_baseline.py --label after --model qwen2.5:7b
    runtime\\python\\python.exe evaluation\\run_baseline.py --compare data\\baseline-before-*.json data\\baseline-after-*.json

- Tự chấm các câu có đáp án khách quan (tính toán, dịch, thơ 4 câu...).
- Các câu còn lại lưu câu trả lời để người chấm 0-4 theo evaluation/README.md.
- Mặc định bỏ qua câu 25-30 (cần tài liệu đính kèm / tài khoản thật).
- Web tắt trừ khi có --web. Không ghi file người dùng; kết quả lưu vào data/.
"""
import argparse
import json
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SKIP_DEFAULT = {25, 26, 27, 28, 29, 30}


def _has(pattern, text):
    return re.search(pattern, text, re.I | re.S) is not None


# Kiểm tra tự động: trả về True/False; None = cần người chấm.
AUTO_CHECKS = {
    3: lambda a: _has(r'nghi[eê]ng', a),
    13: lambda a: _has(r'(?<![\d.,])0[.,]3(?!\d)', a) and '0.30000000000000004' not in a,
    14: lambda a: _has(r'1[.,\s]?020[.,\s]?000', a),
    15: lambda a: _has(r'2[.,\s]?500\s*(m|mét)', a),
    16: lambda a: _has(r'(?<!\d)2\s*ngày', a),
    17: lambda a: len(re.findall(r'(?<![\d.,])5(?:[.,]0+)?(?![\d.,]\d)', a)) >= 2,
    18: lambda a: _has(r'(?<![\d.,])0\s*(°\s*C|độ\s*C)', a),
    20: lambda a: _has(r'(x\s*==\s*0|if\s+not\s+x|ZeroDivisionError)', a),
    21: lambda a: _has(r'GROUP\s+BY', a),
    22: lambda a: _has(r'th[ứu]\s*s[áa]u', a) and _has(r'ho[ãa]n', a),
    24: lambda a: len([l for l in a.strip().splitlines() if l.strip() and not l.strip().startswith(('#', '*', '-', '>'))]) == 4,
}


def _last_answer(state):
    for m in reversed(state.get('messages', [])):
        if m.get('role') == 'assistant' and m.get('content'):
            return m['content']
    return ''


def run(args):
    import ollama
    from assistant.agent import Agent
    from assistant.config import load_config
    from assistant.storage import Store

    cfg = load_config()
    model = args.model or cfg['default_model']
    client = ollama.Client(host=cfg['ollama_host'], timeout=cfg.get('timeout_seconds', 180))
    questions = json.loads((ROOT_DIR / 'evaluation' / 'questions.json').read_text(encoding='utf-8'))
    if args.ids:
        wanted = {int(x) for x in args.ids.split(',')}
        questions = [q for q in questions if q['id'] in wanted]
    elif not args.all:
        questions = [q for q in questions if q['id'] not in SKIP_DEFAULT]

    rows = []
    with tempfile.TemporaryDirectory(prefix='chatai-baseline-') as tmp:
        store = Store(Path(tmp) / 'history.sqlite3')
        for q in questions:
            print(f"[{q['id']:>2}] {q['question']}", flush=True)
            cid = store.create()
            state = store.load(cid)
            tool_calls = 0
            error = None
            t0 = time.perf_counter()
            try:
                agent = Agent(client, None, cfg, store, cid, tools_enabled=not args.no_tools)
                agent.start(state, q['question'], model)
                state.update(ui_mode=4 if args.web else 0, web_search_requested=args.web)
                for event in agent.run(state):
                    if event.get('type') == 'status' and args.verbose:
                        print('    ', event.get('text'), flush=True)
            except Exception as exc:  # ghi lỗi, không dừng cả bộ
                error = f'{type(exc).__name__}: {exc}'
            elapsed = round(time.perf_counter() - t0, 2)
            if state.get('model_error'):
                failure = state['model_error']
                error = f"{failure['type']}: {failure['message']}"
            answer = '' if error else _last_answer(state)
            trace = []
            for m in state.get('messages', [])[1:]:
                if m.get('tool_calls'):
                    for call in m['tool_calls']:
                        fn = call.get('function', {}) if isinstance(call, dict) else {}
                        trace.append({'call': fn.get('name'), 'args': fn.get('arguments')})
                        tool_calls += 1
                elif m.get('role') == 'tool':
                    trace.append({'result_of': m.get('tool_name'), 'result': str(m.get('content', ''))[:400]})
            check = AUTO_CHECKS.get(q['id'])
            auto = None if check is None or not answer else bool(check(answer))
            print(f"     {elapsed}s  auto={auto}  {'LỖI: ' + error if error else ''}", flush=True)
            rows.append({
                'id': q['id'], 'category': q['category'], 'question': q['question'],
                'criteria': q['criteria'], 'answer': answer, 'error': error,
                'seconds': elapsed, 'tool_events': tool_calls, 'trace': trace,
                'has_chinese': bool(re.search(r'[㐀-䶿一-鿿]', answer)),
                'used_web': bool(state.get('web_results')), 'auto_pass': auto,
                'status': 'error' if error else 'answered' if answer else 'empty',
                'manual_scores': {'accuracy': None, 'relevance': None, 'usefulness': None,
                                  'grounding': None, 'clarity': None},
            })

    result = {
        'label': args.label, 'created': datetime.now().isoformat(timespec='seconds'),
        'model': model, 'num_ctx': cfg.get('num_ctx'), 'temperature': cfg.get('temperature'),
        'web': args.web, 'tools': not args.no_tools,
        'summary': summarize(rows), 'rows': rows,
    }
    out = ROOT_DIR / 'data' / f"baseline-{args.label}-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nTÓM TẮT:', json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print('Đã lưu:', out)
    print('Chỉ chấm manual_scores cho câu có status=answered; lỗi kết nối không phải câu trả lời sai.')
    return result


def summarize(rows):
    auto = [r for r in rows if r['auto_pass'] is not None]
    times = [r['seconds'] for r in rows if not r['error']]
    manual = []
    for r in rows:
        s = r.get('manual_scores') or {}
        if not r['error'] and r['answer'] and len(s) == 5 and all(type(v) in (int, float) and 0 <= v <= 4 for v in s.values()):
            manual.append(sum(s.values()))
    return {
        'cases': len(rows),
        'errors': sum(1 for r in rows if r['error']),
        'empty_answers': sum(1 for r in rows if not r['answer']),
        'auto_pass': f"{sum(1 for r in auto if r['auto_pass'])}/{len(auto)}",
        'auto_failed_ids': [r['id'] for r in auto if not r['auto_pass']],
        'used_web_ids': [r['id'] for r in rows if r['used_web']],
        'chinese_ids': [r['id'] for r in rows if r.get('has_chinese')],
        'avg_seconds': round(sum(times) / len(times), 2) if times else None,
        'max_seconds': max(times) if times else None,
        'manual_scored': len(manual),
        'manual_mean_out_of_20': round(sum(manual) / len(manual), 2) if manual else None,
    }


def compare(before_path, after_path):
    b = json.loads(Path(before_path).read_text(encoding='utf-8'))
    a = json.loads(Path(after_path).read_text(encoding='utf-8'))
    sb, sa = summarize(b['rows']), summarize(a['rows'])
    bmap = {r['id']: r for r in b['rows']}
    changes = []
    for r in a['rows']:
        old = bmap.get(r['id'])
        if old and old['auto_pass'] != r['auto_pass']:
            changes.append({'id': r['id'], 'before': old['auto_pass'], 'after': r['auto_pass']})
    print(json.dumps({'before': {'model': b['model'], **sb}, 'after': {'model': a['model'], **sa},
                      'auto_changes': changes}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--label', default='before', help='Nhãn lần chạy, vd before/after')
    p.add_argument('--model', help='Model Ollama; mặc định lấy default_model trong config.json')
    p.add_argument('--ids', help='Chỉ chạy các ID, vd 13,14,15')
    p.add_argument('--all', action='store_true', help='Chạy cả câu 25-30')
    p.add_argument('--web', action='store_true', help='Bật tìm kiếm mạng')
    p.add_argument('--no-tools', action='store_true', help='Tắt công cụ AI')
    p.add_argument('--verbose', action='store_true')
    p.add_argument('--compare', nargs=2, metavar=('BEFORE', 'AFTER'))
    args = p.parse_args()
    if args.compare:
        compare(*args.compare)
    else:
        result = run(args)
        return 1 if result['summary']['errors'] or result['summary']['empty_answers'] else 0


if __name__ == '__main__':
    sys.exit(main())
