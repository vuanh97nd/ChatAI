"""Local, credential-free timings. Recording never reads or writes Drive files."""
import math
import time
from collections import deque
from contextlib import contextmanager
from threading import Lock

_rows=deque(maxlen=64)
_lock=Lock()
REVISION='startup-login-3'


def record(stage,seconds):
    if not isinstance(stage,str) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<0:
        raise ValueError('Invalid timing')
    with _lock:_rows.append((stage,round(seconds,3)))


@contextmanager
def measure(stage):
    start=time.monotonic()
    try:yield
    finally:record(stage,time.monotonic()-start)


def report():
    with _lock:rows=list(_rows)
    return 'ChatAI performance '+REVISION+'\n'+'\n'.join(f'{stage}: {seconds:.3f} s' for stage,seconds in rows)
