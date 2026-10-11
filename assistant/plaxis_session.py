"""Session references are valid only for the live project and generated soil topology."""
import hashlib
import json


def local_guid(obj):
    try:
        value=object.__getattribute__(obj,'_guid')
        return value if isinstance(value,str) and value else None
    except (AttributeError,TypeError):
        return None


def live_scope(g,version,port):
    try:
        project=local_guid(g.Project)
        initial=local_guid(g.InitialPhase)
        soils=[local_guid(obj) for obj in g.Soils]
        if not project or not initial or any(value is None for value in soils):return None
        return hashlib.sha256(json.dumps([version,port,project,initial,soils]).encode()).hexdigest()
    except Exception:
        return None


def invalidate(session):
    for key in ('aliases','created','phase_log'):
        session[key]={}
    for key in ('stage_permit','excavation_draws','seen'):
        session.pop(key,None)


def bind(session,scope):
    changed=scope is None or session.get('live_scope')!=scope
    if changed:invalidate(session)
    session['live_scope']=scope
    return changed
