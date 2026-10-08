"""Resolve short approvals against the latest explicit tutorial proposal, not an old run."""
import json
import re

_ACK=re.compile(r'^\s*(?:ok(?:\s+rồi)?|đồng\s+ý|chạy(?:\s+lại)?|thử\s+lại(?:\s+nhé)?|có[,. ]*(?:fix|sửa)(?:\s+lại)?(?:\s+nhé)?|fix\s+lại(?:\s+nhé)?)\s*[.!]?\s*$',re.I)


def tutorial_proposal(text):
    title='drained and undrained stability of an embankment'
    if title not in text.casefold():return None
    # This recipe is specific to the verified chapter-2 exercise; do not guess
    # another project's dimensions or overwrite material parameters from that project.
    if not re.search(r'(?:cao|height)[^\n]{0,30}\b4(?:[.,]0)?\s*m',text,re.I):return None
    if not re.search(r'(?:đỉnh|top)[^\n]{0,45}\b2(?:[.,]0)?\s*m',text,re.I):return None
    if not re.search(r'tạo.*script|sinh.*script|chạy\s+trực\s+tiếp',text,re.I):return None
    from .plaxis_app import _validate_problem
    problem=_validate_problem(json.dumps({'type':'embankment_stability','embankment_height':4.0,
                                          'embankment_top_width':2.0,'clay_thickness':6.0,
                                          'slope_left':2.0,'slope_right':3.0}))
    return {'version':'2d','project_name':'Embankment_Drained_Undrained',
            'problem':json.dumps(problem,ensure_ascii=False)}


def confirmation_call(prompt,state,has_remote,has_app):
    if not _ACK.fullmatch(prompt):return None
    messages=state.get('messages',[])
    # A newer proposal overrides the older slope tool call. Successful execution
    # closes the proposal; an explicit retry can still use the accepted task.
    proposed=False
    previous=messages[:-1] if messages and messages[-1].get('role')=='user' else messages
    for m in reversed(previous):
        if m.get('role')=='assistant' and isinstance(m.get('content'),str):
            proposal=tutorial_proposal(m['content'])
            if proposal:
                state['plaxis_active_problem']=proposal
                proposed=True
                break
        if m.get('tool_calls') or m.get('role')=='user':break
    # A bare acknowledgement after completion or a new topic is not a retry.
    if not proposed and prompt.strip().casefold().rstrip('.!') in ('ok','ok rồi','đồng ý'):
        return None
    args=active_problem(state)
    if not args:return None
    if has_remote:name='plaxis_run_problem'
    elif has_app:name='plaxis_generate_script'
    else:return None
    args={k:v for k,v in args.items() if k in ('version','problem','project_name')}
    return {'function':{'name':name,'arguments':args}}

def active_problem(state):
    value=state.get('plaxis_active_problem')
    if not isinstance(value,dict) or value.get('version') not in ('2d','3d'):return None
    if not isinstance(value.get('problem'),str) or len(value['problem'].encode())>50000:return None
    if not isinstance(value.get('project_name'),str) or not 1<=len(value['project_name'])<=100:return None
    return {k:value[k] for k in ('version','problem','project_name')}
