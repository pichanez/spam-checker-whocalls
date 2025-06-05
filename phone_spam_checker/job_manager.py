import asyncio
import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol

from .exceptions import JobAlreadyRunningError

from .domain.models import PhoneCheckResult, CheckStatus


class JobRepository(Protocol):
    """Interface for job storage backends."""

    def new_job(self, devices: List[str]) -> str:
        """Create a new job for given devices and return its identifier."""

    def complete_job(self, job_id: str, results: List[PhoneCheckResult]) -> None:
        """Mark a job as completed and store results."""

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed."""

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return job info or ``None`` if not found."""

    def ensure_no_running(self, device: str) -> None:
        """Raise an exception if there is a job in progress for this device."""

    def cleanup(self) -> None:
        """Delete old jobs from storage."""


class SQLiteJobRepository(JobRepository):
    """Job repository backed by a SQLite database."""

    JOB_TTL = timedelta(hours=1)

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS jobs ("
            "job_id TEXT PRIMARY KEY,"
            "status TEXT,"
            "devices TEXT,"
            "results TEXT,"
            "error TEXT,"
            "created_at TEXT"
            ")"
        )
        self._db.commit()

    def new_job(self, devices: List[str]) -> str:
        job_id = uuid.uuid4().hex
        devices_str = ",".join(devices)
        with self._lock:
            self._db.execute(
                "INSERT INTO jobs(job_id, status, devices, results, error, created_at) VALUES(?,?,?,?,?,?)",
                (
                    job_id,
                    "in_progress",
                    devices_str,
                    None,
                    None,
                    datetime.utcnow().isoformat(),
                ),
            )
            self._db.commit()
        return job_id

    def complete_job(self, job_id: str, results: List[PhoneCheckResult]) -> None:
        serializable = []
        for r in results:
            if is_dataclass(r):
                item = asdict(r)
            elif hasattr(r, "dict"):
                item = r.dict()
            else:
                item = dict(r)
            status = item.get("status")
            if hasattr(status, "value"):
                item["status"] = status.value
            serializable.append(item)
        results_json = json.dumps(serializable)
        with self._lock:
            self._db.execute(
                "UPDATE jobs SET status=?, results=? WHERE job_id=?",
                ("completed", results_json, job_id),
            )
            self._db.commit()

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE jobs SET status=?, error=? WHERE job_id=?",
                ("failed", error, job_id),
            )
            self._db.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._db.execute(
                "SELECT status, results, error, created_at FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        status, results_json, error, created_at = row
        results = None
        if results_json:
            try:
                data = json.loads(results_json)
                for entry in data:
                    status = entry.get("status")
                    if isinstance(status, str):
                        try:
                            entry["status"] = CheckStatus(status)
                        except Exception:
                            pass
                results = [PhoneCheckResult(**entry) for entry in data]
            except Exception:
                results = None
        return {
            "status": status,
            "results": results,
            "error": error,
            "created_at": datetime.fromisoformat(created_at),
        }

    def ensure_no_running(self, device: str) -> None:
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM jobs WHERE status='in_progress' AND instr(devices, ?) > 0 LIMIT 1",
                (device,),
            ).fetchone()
        if row:
            raise JobAlreadyRunningError(
                f"Previous task is still in progress for {device}"
            )

    def cleanup(self) -> None:
        limit = datetime.utcnow() - self.JOB_TTL
        with self._lock:
            self._db.execute(
                "DELETE FROM jobs WHERE created_at < ?", (limit.isoformat(),)
            )
            self._db.commit()


class JobManager:
    """Thin wrapper delegating operations to a repository."""

    CLEANUP_INTERVAL_SECONDS = 60

    def __init__(self, repo: JobRepository) -> None:
        self._repo = repo

    def new_job(self, devices: List[str]) -> str:
        return self._repo.new_job(devices)

    def complete_job(self, job_id: str, results: List[PhoneCheckResult]) -> None:
        self._repo.complete_job(job_id, results)

    def fail_job(self, job_id: str, error: str) -> None:
        self._repo.fail_job(job_id, error)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._repo.get_job(job_id)

    def ensure_no_running(self, device: str) -> None:
        self._repo.ensure_no_running(device)

    async def cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
            self._repo.cleanup()
