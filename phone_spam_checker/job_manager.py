import asyncio
import json
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Text,
    DateTime,
    select,
    insert,
    update,
)
from sqlalchemy.engine import Engine
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


class BaseJobRepository(JobRepository, ABC):
    """Abstract base class for DB-backed job repositories."""

    JOB_TTL = timedelta(hours=1)

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ``new_job`` remains abstract for subclasses
    @abstractmethod
    def new_job(self, devices: List[str]) -> str:
        pass

    @abstractmethod
    def _update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        results: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update fields of a job."""

    @abstractmethod
    def _get_job_row(self, job_id: str) -> Optional[tuple]:
        """Return a raw job row."""

    @abstractmethod
    def _has_running_job(self, device: str) -> bool:
        """Return ``True`` if there is a running job for the device."""

    @abstractmethod
    def _delete_old_jobs(self, limit: datetime) -> None:
        """Delete jobs older than ``limit``."""

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
            services = item.get("services")
            if isinstance(services, list):
                for svc in services:
                    st = svc.get("status")
                    if hasattr(st, "value"):
                        svc["status"] = st.value
            serializable.append(item)
        results_json = json.dumps(serializable)
        with self._lock:
            self._update_job(job_id, status="completed", results=results_json)

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            self._update_job(job_id, status="failed", error=error)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_job_row(job_id)
        if not row:
            return None
        status, results_json, error, created_at = row
        results = None
        if results_json:
            try:
                data = json.loads(results_json)
                for entry in data:
                    st = entry.get("status")
                    if isinstance(st, str):
                        try:
                            entry["status"] = CheckStatus(st)
                        except Exception:
                            pass
                    services = entry.get("services")
                    if isinstance(services, list):
                        for svc in services:
                            st2 = svc.get("status")
                            if isinstance(st2, str):
                                try:
                                    svc["status"] = CheckStatus(st2)
                                except Exception:
                                    pass
                results = data
            except Exception:
                results = None
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return {
            "status": status,
            "results": results,
            "error": error,
            "created_at": created_at,
        }

    def ensure_no_running(self, device: str) -> None:
        with self._lock:
            running = self._has_running_job(device)
        if running:
            raise JobAlreadyRunningError(
                f"Previous task is still in progress for {device}"
            )

    def cleanup(self) -> None:
        limit = datetime.utcnow() - self.JOB_TTL
        with self._lock:
            self._delete_old_jobs(limit)


class SQLiteJobRepository(BaseJobRepository):
    """Job repository backed by a SQLite database."""

    def __init__(self, db_path: str) -> None:
        super().__init__()
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

    def _update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        results: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        fields = []
        values = []
        if status is not None:
            fields.append("status=?")
            values.append(status)
        if results is not None:
            fields.append("results=?")
            values.append(results)
        if error is not None:
            fields.append("error=?")
            values.append(error)
        values.append(job_id)
        self._db.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE job_id=?",
            tuple(values),
        )
        self._db.commit()

    def _get_job_row(self, job_id: str) -> Optional[tuple]:
        return self._db.execute(
            "SELECT status, results, error, created_at FROM jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()

    def _has_running_job(self, device: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM jobs WHERE status='in_progress' AND instr(devices, ?) > 0 LIMIT 1",
            (device,),
        ).fetchone()
        return row is not None

    def _delete_old_jobs(self, limit: datetime) -> None:
        self._db.execute("DELETE FROM jobs WHERE created_at < ?", (limit.isoformat(),))
        self._db.commit()


class PostgresJobRepository(BaseJobRepository):
    """Job repository backed by a PostgreSQL database."""

    def __init__(self, dsn: str) -> None:
        super().__init__()
        self._engine: Engine = create_engine(dsn)
        metadata = MetaData()
        self._table = Table(
            "jobs",
            metadata,
            Column("job_id", String, primary_key=True),
            Column("status", String),
            Column("devices", String),
            Column("results", Text),
            Column("error", Text),
            Column("created_at", DateTime),
        )
        metadata.create_all(self._engine)

    def new_job(self, devices: List[str]) -> str:
        job_id = uuid.uuid4().hex
        devices_str = ",".join(devices)
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                insert(self._table).values(
                    job_id=job_id,
                    status="in_progress",
                    devices=devices_str,
                    results=None,
                    error=None,
                    created_at=datetime.utcnow(),
                )
            )
        return job_id

    def _update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        results: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        values: Dict[str, Any] = {}
        if status is not None:
            values["status"] = status
        if results is not None:
            values["results"] = results
        if error is not None:
            values["error"] = error
        with self._engine.begin() as conn:
            conn.execute(
                update(self._table)
                .where(self._table.c.job_id == job_id)
                .values(**values)
            )

    def _get_job_row(self, job_id: str) -> Optional[tuple]:
        with self._engine.begin() as conn:
            return conn.execute(
                select(
                    self._table.c.status,
                    self._table.c.results,
                    self._table.c.error,
                    self._table.c.created_at,
                ).where(self._table.c.job_id == job_id)
            ).first()

    def _has_running_job(self, device: str) -> bool:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(self._table.c.job_id)
                .where(
                    (self._table.c.status == "in_progress")
                    & (self._table.c.devices.like(f"%{device}%"))
                )
                .limit(1)
            ).first()
        return row is not None

    def _delete_old_jobs(self, limit: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(self._table.delete().where(self._table.c.created_at < limit))


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
