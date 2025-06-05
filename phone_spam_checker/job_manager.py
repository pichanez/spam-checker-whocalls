import asyncio
import json
import sqlite3
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .domain.models import PhoneCheckResult


class JobManager:
    """Persistent job storage based on SQLite."""

    CLEANUP_INTERVAL_SECONDS = 60
    JOB_TTL = timedelta(hours=1)

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS jobs ("
            "job_id TEXT PRIMARY KEY,"
            "status TEXT,"
            "results TEXT,"
            "error TEXT,"
            "created_at TEXT"
            ")"
        )
        self._db.commit()

    def new_job(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._db.execute(
                "INSERT INTO jobs(job_id, status, results, error, created_at) VALUES(?,?,?,?,?)",
                (job_id, "in_progress", None, None, datetime.utcnow().isoformat()),
            )
            self._db.commit()
        return job_id

    def complete_job(self, job_id: str, results: List[PhoneCheckResult]) -> None:
        results_json = json.dumps([asdict(r) for r in results])
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
                results = [PhoneCheckResult(**r) for r in data]
            except Exception:
                results = None
        return {
            "status": status,
            "results": results,
            "error": error,
            "created_at": datetime.fromisoformat(created_at),
        }

    def ensure_no_running(self) -> None:
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM jobs WHERE status='in_progress' LIMIT 1"
            ).fetchone()
        if row:
            raise HTTPException(status_code=429, detail="Previous task is still in progress")

    async def cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
            self._cleanup()

    def _cleanup(self) -> None:
        limit = datetime.utcnow() - self.JOB_TTL
        with self._lock:
            self._db.execute(
                "DELETE FROM jobs WHERE created_at < ?", (limit.isoformat(),)
            )
            self._db.commit()
