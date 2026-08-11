"""Lightweight in-process async job queue for batch inference (single-worker)."""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


def async_jobs_enabled() -> bool:
    return os.environ.get("ASYNC_JOBS_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


@dataclass
class Job:
    job_id: str
    status: str = "queued"  # queued|running|succeeded|failed
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class JobQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._pending: list[tuple[str, Callable[[], dict[str, Any]]]] = []
        self._worker = threading.Thread(target=self._run, name="async-jobs", daemon=True)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._worker.start()

    def submit(self, fn: Callable[[], dict[str, Any]]) -> str:
        self.start()
        job_id = uuid.uuid4().hex
        with self._cv:
            self._jobs[job_id] = Job(job_id=job_id)
            self._pending.append((job_id, fn))
            self._cv.notify()
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._pending:
                    self._cv.wait()
                job_id, fn = self._pending.pop(0)
                job = self._jobs[job_id]
                job.status = "running"
                job.started_at = time.time()
            try:
                result = fn()
                with self._lock:
                    job.status = "succeeded"
                    job.result = result
                    job.finished_at = time.time()
            except Exception as exc:  # noqa: BLE001 — surfaced to client
                with self._lock:
                    job.status = "failed"
                    job.error = str(exc)
                    job.finished_at = time.time()


JOB_QUEUE = JobQueue()
