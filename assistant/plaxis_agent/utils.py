"""One process-wide lock for native calls, including the existing desktop path."""
import functools
import logging
import threading
from collections.abc import Callable
from typing import Any

NATIVE_LOCK = threading.RLock()
logger = logging.getLogger('chatai.plaxis_agent')


def serialized_native(function: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        with NATIVE_LOCK:
            return function(*args, **kwargs)
    return wrapped
