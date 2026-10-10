"""Keep useful dialogue in provider context without truncating every answer to 1600 chars."""


def clip(text,size):
    """Keep the opening and the conclusion of a long message; answers usually end with the decision."""
    if len(text)<=size:return text
    if size<200:return text[:size]
    marker='\n[…lược bớt '+str(len(text)-size)+' ký tự…]\n'
    room=size-len(marker);head=room*2//3
    return text[:head]+marker+text[-(room-head):]


def conversation_context(messages,online=True):
    rows=[{'role':m['role'],'content':m['content']} for m in messages
          if m.get('role') in ('user','assistant') and isinstance(m.get('content'),str) and m['content']]
    limit=36 if online else 20
    budget=90000 if online else 14000
    selected=[]
    for m in reversed(rows[-limit:]):
        if budget<=0:break
        text=clip(m['content'],min(12000,budget))
        selected.append({'role':m['role'],'content':text});budget-=len(text)
    selected.reverse()
    if online and len(rows)>len(selected):
        earlier=rows[:-len(selected)] if selected else rows
        parts=[];remaining=8000
        for m in reversed(earlier):
            # Agreed values often come from an assistant proposal the user accepted.
            size=2000 if m['role']=='user' else 800
            text=clip(m['content'],min(size,remaining))
            parts.append(('Người dùng: ' if m['role']=='user' else 'AI đã trả lời: ')+text);remaining-=len(text)
            if remaining<=0:break
        if parts:
            summary='Thông tin ở các lượt trước (xếp từ cũ đến mới; dùng khi còn liên quan):\n'+'\n'.join(reversed(parts))
            if selected and selected[0]['role']=='user':
                # Merge instead of sending two consecutive user turns, which some providers reject.
                selected[0]={'role':'user','content':summary+'\n\n---\n'+selected[0]['content']}
            else:selected.insert(0,{'role':'user','content':summary})
    return selected
