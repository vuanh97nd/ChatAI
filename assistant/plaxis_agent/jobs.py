"""Bounded in-memory jobs. Native writes are never replayed after restart."""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from .agent import run_agent
from .schemas import JobRequest
from .utils import logger


@dataclass
class Job:
    id: str
    request: JobRequest
    status: str = 'queued'
    created: float = field(default_factory=time.time)
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)

    def public(self) -> dict[str, Any]:
        return {'id': self.id, 'status': self.status, 'created': self.created,
                'events': list(self.events), 'result': self.result}


class Jobs:
    def __init__(self, model: Any, runtime: Any, capacity: int = 32) -> None:
        self.model, self.runtime, self.capacity = model, runtime, capacity
        self.jobs: dict[str, Job] = {}
        self.tasks: set[asyncio.Task[Any]] = set()
        self.lock = asyncio.Lock()

    def submit(self, request: JobRequest) -> Job:
        if len(self.jobs) >= self.capacity:
            terminal = next((key for key, job in self.jobs.items() if job.status in {'finished', 'failed', 'stopped'}), None)
            if terminal is None:
                raise RuntimeError('Hàng đợi đầy; chờ công việc hiện tại kết thúc.')
            del self.jobs[terminal]
        job = Job(id=uuid.uuid4().hex, request=request)
        self.jobs[job.id] = job
        task = asyncio.create_task(self.run(job))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def run(self, job: Job) -> None:
        # Hold for the whole workflow: two API jobs cannot mix native project state.
        async with self.lock:
            if job.stop.is_set():
                job.status = 'stopped'
                return
            job.status = 'running'
            logger.info('job_start id=%s version=%s', job.id, job.request.version)
            try:
                job.result = await run_agent(self.model, self.runtime, job.request.prompt,
                    job.request.version, job.request.max_steps, job.stop, job.events)
                job.status = 'stopped' if job.stop.is_set() else 'failed' if job.result['halted'] or job.result['limit_reached'] else 'finished'
            except Exception as error:
                logger.exception('job_failed id=%s', job.id)
                job.result = {'error': str(error)[:1000], 'model_completion_verified': False}
                job.status = 'failed'
            logger.info('job_end id=%s status=%s', job.id, job.status)

    async def close(self) -> None:
        for job in self.jobs.values():
            job.stop.set()
        # Let a current native call report its actual result; no forced task cancellation.
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
        self.runtime.close()
