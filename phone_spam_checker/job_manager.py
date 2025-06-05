import asyncio
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .domain.models import PhoneCheckResult


class JobManager:
    """In-memory job storage and lifecycle management."""

    CLEANUP_INTERVAL_SECONDS = 60
    JOB_TTL = timedelta(hours=1)

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def new_job(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "status": "in_progress",
                "results": None,
                "error": None,
                "created_at": datetime.utcnow(),
            }
        return job_id

    def complete_job(self, job_id: str, results: List[PhoneCheckResult]) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "completed"
                self._jobs[job_id]["results"] = results

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = error

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._jobs.get(job_id)

    def ensure_no_running(self) -> None:
        with self._lock:
            if any(info.get("status") == "in_progress" for info in self._jobs.values()):
                raise HTTPException(status_code=429, detail="Previous task is still in progress")

    async def cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
            self._cleanup()

    def _cleanup(self) -> None:
        now = datetime.utcnow()
        with self._lock:
            outdated = [
                jid
                for jid, info in self._jobs.items()
                if now - info.get("created_at", now) > self.JOB_TTL
            ]
            for jid in outdated:
                del self._jobs[jid]
