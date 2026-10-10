"""Render calculator observations without trusting numeric claims in model prose."""
from .answer_policy import turn_tools


def calculation_answer(state):
    rows=[r['result'] for r in turn_tools(state) if r['name']=='calculate']
    outputs=[]
    for result in rows:
        if result.get('ok') is not True:continue
        if 'result' in result:
            value=str(result['result']).replace('.',',')
            unit=str(result.get('unit') or '')
            line='Kết quả: '+value+(' '+unit if unit else '')+'.'
            expression=result.get('normalized_expression') or result.get('expression')
            if expression:line+='\nPhép tính đã thực hiện: `'+str(expression)+'`.'
            if result.get('input'):line+='\nGiá trị đầu vào: '+str(result['input'])+'.'
            outputs.append(line)
        elif 'mean' in result:
            names=(('count','Số giá trị'),('sum','Tổng'),('mean','Trung bình'),('median','Trung vị'),('min','Nhỏ nhất'),('max','Lớn nhất'))
            outputs.append('\n'.join(label+': '+str(result[key]).replace('.',',') for key,label in names))
        elif 'days' in result:
            outputs.append('Chênh lệch: '+str(result['days'])+' ngày. '+str(result.get('note','')))
        elif 'datetime' in result:
            outputs.append('Thời gian: '+str(result['datetime'])+' ('+str(result.get('timezone',''))+').')
    if not outputs:
        note='Chưa nhận được kết quả từ công cụ tính nên tôi chưa thể xác nhận đáp số. Hãy ghi rõ phép tính, số liệu và đơn vị để tính bằng Python.'
        if rows and rows[-1].get('error'):note+='\nCông cụ báo: '+str(rows[-1]['error'])[:600]
        return note
    if any(r.get('ok') is not True for r in rows):
        outputs.append('Có lần gọi công cụ chưa thành công; các kết quả trên chỉ xác nhận những phép tính đã thực hiện được.')
    return '\n\n'.join(outputs)
