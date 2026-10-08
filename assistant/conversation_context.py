"""Keep useful dialogue in provider context without truncating every answer to 1600 chars."""
def conversation_context(messages,online=True):
    rows=[{'role':m['role'],'content':m['content']} for m in messages
          if m.get('role') in ('user','assistant') and isinstance(m.get('content'),str) and m['content']]
    limit=36 if online else 20
    budget=90000 if online else 14000
    selected=[]
    for m in reversed(rows[-limit:]):
        if budget<=0:break
        text=m['content'][:min(12000,budget)]
        selected.append({'role':m['role'],'content':text});budget-=len(text)
    selected.reverse()
    if online and len(rows)>len(selected):
        earlier=rows[:-len(selected)] if selected else rows
        parts=[];remaining=8000
        for m in reversed(earlier):
            if m['role']!='user':continue
            text=m['content'][:min(2000,remaining)]
            parts.append(text);remaining-=len(text)
            if remaining<=0:break
        if parts:selected.insert(0,{'role':'user','content':'Thông tin người dùng đã nêu ở các lượt trước (xếp từ cũ đến mới; dùng khi còn liên quan):\n'+'\n'.join(reversed(parts))})
    return selected
