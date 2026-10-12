"""Compact NVIDIA planning context only; state and execution guards stay intact."""
import copy
import json

GUIDE = ('\nQUY TRÌNH NVIDIA: chỉ chọn bước kế tiếp còn thiếu. arguments là object JSON; '
         'plaxis_commands.commands là mảng object trực tiếp, tối đa 3 lệnh khi chẩn đoán lỗi. '
         'Không sao chép JSON lồng chuỗi từ lời gọi cũ đã lỗi. '
         'Sau mesh, dùng gotostages rồi inspect_progress/inspect_stage để đọc soil cluster thật; '
         'hình học staged thường nằm ở Parent.BoundingBox, không đoán BoundingBox.YMin/YMax trên Soil. '
         'Không hỏi người dùng biên cluster có thể đọc từ mô hình. '
         'Không đổi Active khi chưa xác định cả vùng X/Y và phase. '
         'Lệnh thành công được giữ; chỉ sửa phần thiếu/sai. '
         'Chỉ tra web/manual khi thiếu dữ kiện hoặc cú pháp cụ thể; không đọc lại nguồn đã đủ. '
         'Ngữ cảnh có đánh dấu rút gọn không phải toàn bộ kết quả; cần thêm số liệu thì đọc đúng đối tượng, '
         'không suy đoán, không báo đã xác minh/hoàn tất chỉ từ bản trích.')


def schemas_for_nvidia(schemas):
    """Retain every parameter/requirement; shorten descriptions, not validation."""
    result=copy.deepcopy(schemas)
    for spec in result:
        fn=spec.get('function',{})
        description=fn.get('description','')
        if len(description)>1200:
            fn['description']=description[:1200]+' [Mô tả rút gọn; tham số và kiểm tra công cụ vẫn đầy đủ.]'
    return result


def excerpt(text,limit):
    if len(text)<=limit:return text
    return text[:limit]+'\n[Ngữ cảnh rút gọn; không suy ra phần bị lược bỏ.]'


def messages_for_nvidia(state,instruction):
    from .prompts import CONTINUITY
    from .online_automation import image_message_content
    history=state['messages']
    user_index=max((i for i,m in enumerate(history) if m.get('role')=='user'),default=-1)
    messages=[{'role':'system','content':instruction+CONTINUITY+GUIDE}]
    prior=[m for m in history[:user_index] if m.get('role')=='user' and m.get('content')]
    if prior:
        messages.append({'role':'system','content':'Yêu cầu trước để nối tiếp công việc (chưa phải bằng chứng đã làm):\n'+
                         '\n'.join(excerpt(m['content'],3000) for m in prior[-2:])})
    if user_index>=0:
        current=history[user_index]
        text=current.get('content','')[:60000]
        messages.append({'role':'user','content':image_message_content(text,current['images'][0]) if current.get('images') else text})
    # Latest results take priority. Old tool-call arguments may contain the very
    # escaping error the model needs to stop copying; show names, not examples.
    selected=[];budget=24000
    tools=[i for i,m in enumerate(history) if m.get('role')=='tool']
    latest_tool=tools[-1] if tools else -1
    latest_image=max((i for i,m in enumerate(history) if i>user_index and m.get('role')=='tool' and m.get('images')),default=-1)
    for i in range(len(history)-1,max(-1,len(history)-13),-1):
        m=history[i]
        if m.get('role')=='user':continue
        if m.get('role')=='tool':
            label='KẾT QUẢ LƯỢT HIỆN TẠI' if i>user_index else 'KẾT QUẢ LỊCH SỬ (chưa đọc lại trong lượt này)'
            content=label+' '+m.get('tool_name','tool')+': '+excerpt(str(m.get('content','')),12000 if i==latest_tool else 2000)
        elif m.get('content'):
            content='Phản hồi AI trước, chưa phải bằng chứng: '+excerpt(m['content'],1200)
        elif m.get('tool_calls'):
            calls=m['tool_calls'];fn=(calls[0] or {}).get('function',{}) if isinstance(calls,list) else {}
            content=json.dumps({'previous_tool':fn.get('name',''),'note':'Xem kết quả công cụ, không lặp lại lời gọi cũ.'},ensure_ascii=False)
        else:continue
        if len(content)>budget:continue
        rendered=image_message_content(content,m['images'][0]) if i==latest_image else content
        selected.append({'role':'user' if m.get('role')=='tool' else 'assistant','content':rendered})
        budget-=len(content)
    messages.extend(reversed(selected))
    return messages
