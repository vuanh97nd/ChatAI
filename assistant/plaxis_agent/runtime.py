"""Run blocking native calls off the FastAPI event loop, one worker per service."""
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from .tools import execute


class NativeRuntime:
    def __init__(self, remote: Any) -> None:
        self.remote = remote
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='plaxis-native')

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        # Shield prevents cancellation from pretending an in-flight native write stopped.
        future = loop.run_in_executor(self.executor, functools.partial(execute, self.remote, name, arguments))
        return await asyncio.shield(future)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
