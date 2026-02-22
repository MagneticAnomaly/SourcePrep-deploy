"""Task scheduler for background jobs and periodic tasks."""

import time
import threading
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """A scheduled background job."""
    id: str
    name: str
    func: Callable
    interval_seconds: Optional[int] = None
    status: JobStatus = JobStatus.PENDING
    last_run: Optional[float] = None
    error: Optional[str] = None


class TaskScheduler:
    """Schedule and manage recurring background tasks."""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._running = False

    def add_job(self, job_id: str, name: str, func: Callable, interval_seconds: int) -> Job:
        job = Job(id=job_id, name=name, func=func, interval_seconds=interval_seconds)
        self._jobs[job_id] = job
        logger.info("Scheduled job %s every %ds", name, interval_seconds)
        return job

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.CANCELLED
            return True
        return False

    def run_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status == JobStatus.CANCELLED:
            return False
        try:
            job.status = JobStatus.RUNNING
            job.func()
            job.status = JobStatus.COMPLETED
            job.last_run = time.time()
            return True
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            logger.error("Job %s failed: %s", job.name, e)
            return False

    def get_status(self) -> List[Dict[str, Any]]:
        return [
            {"id": j.id, "name": j.name, "status": j.status.value, "last_run": j.last_run}
            for j in self._jobs.values()
        ]
