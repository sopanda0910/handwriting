"""Job queue (GOALS §5.4: a real queue from day one).

A 25-page batch is a minutes-long async job — never request/response. The
alpha ships an in-process worker pool behind the same interface a Redis-backed
queue will implement later (docs/decisions/0003). Job state lives in the
`jobs` table either way, so batch progress is inspectable from the UI and the
swap is invisible to callers.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from ..config import settings
from ..db import session_scope
from ..models import Job, utcnow

Handler = Callable[[dict], None]

_handlers: dict[str, Handler] = {}


def register_handler(kind: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _handlers[kind] = fn
        return fn
    return decorator


class JobQueue(Protocol):
    def enqueue(self, kind: str, payload: dict) -> str:
        """Persist a Job row and schedule it. Returns the job id."""
        ...


class InProcessQueue:
    """Thread-pool worker in the API process. Dev/alpha only."""

    def __init__(self, workers: int | None = None) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=workers or settings.queue_workers,
            thread_name_prefix="hwp-job",
        )
        self._lock = threading.Lock()

    def enqueue(self, kind: str, payload: dict) -> str:
        if kind not in _handlers:
            raise ValueError(f"No handler registered for job kind {kind!r}")
        with session_scope() as session:
            job = Job(kind=kind, payload=payload, status="queued")
            session.add(job)
            session.flush()
            job_id = job.id
        self._executor.submit(self._run, job_id, kind, payload)
        return job_id

    def _run(self, job_id: str, kind: str, payload: dict) -> None:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            job.status = "running"
            job.started_at = utcnow()
        try:
            _handlers[kind](payload)
        except Exception:
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is not None:
                    job.status = "failed"
                    job.error = traceback.format_exc()
                    job.finished_at = utcnow()
            return
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "done"
                job.finished_at = utcnow()

    def wait_idle(self) -> None:
        """Testing hook: block until all submitted jobs finish."""
        self._executor.shutdown(wait=True)
        self._executor = ThreadPoolExecutor(
            max_workers=settings.queue_workers, thread_name_prefix="hwp-job"
        )


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        if settings.queue_backend == "inprocess":
            _queue = InProcessQueue()
        else:
            raise ValueError(f"Unknown queue backend: {settings.queue_backend!r}")
    return _queue
