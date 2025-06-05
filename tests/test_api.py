import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import sys
import types
from pathlib import Path
import os

sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("API_KEY", "testkey")
os.environ.setdefault("SECRET_KEY", "secret")

from phone_spam_checker.logging_config import configure_logging
from phone_spam_checker.config import settings
from phone_spam_checker.job_manager import JobRepository, JobManager

configure_logging(
    level=settings.log_level,
    fmt=settings.log_format,
    log_file=settings.log_file,
)

import api


class DummyRepository(JobRepository):
    def __init__(self, job_data=None):
        self.job_data = job_data or {}

    def new_job(self, devices):
        return "job123"

    def ensure_no_running(self, device):
        pass

    def get_job(self, job_id):
        return self.job_data.get(job_id)

    def complete_job(self, job_id, results):
        self.job_data[job_id] = {
            "status": "completed",
            "results": results,
            "error": None,
            "created_at": datetime.utcnow(),
        }

    def fail_job(self, job_id, error):
        self.job_data[job_id] = {
            "status": "failed",
            "results": None,
            "error": error,
            "created_at": datetime.utcnow(),
        }

    def cleanup(self):
        pass


class DummyJobManager(JobManager):
    def __init__(self):
        super().__init__(DummyRepository())

    def ensure_no_running(self, device) -> None:
        pass


def _auth_header(client: TestClient) -> dict[str, str]:
    resp = client.post("/login", headers={"X-API-Key": api.settings.api_key})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_submit_check(monkeypatch):
    monkeypatch.setattr(api, "job_manager", JobManager(DummyRepository()))
    monkeypatch.setattr(api, "_new_job", lambda service: "job123")
    called = {}

    async def fake_enqueue(job_id, numbers, service):
        called["task"] = (job_id, numbers, service)

    monkeypatch.setattr(api, "enqueue_job", fake_enqueue)

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["123"], "service": "getcontact"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"job_id": "job123"}


def test_get_status(monkeypatch):
    results = [
        api.CheckResult(phone_number="123", status=api.CheckStatus.SAFE, details="")
    ]
    job_data = {
        "job123": {
            "status": "completed",
            "results": results,
            "error": None,
            "created_at": datetime.utcnow(),
        }
    }
    monkeypatch.setattr(api, "job_manager", JobManager(DummyRepository(job_data)))

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.get(
        "/status/job123",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["results"][0]["phone_number"] == "123"


async def _dummy_run_check(job_id, numbers, service):
    manager = api.job_manager
    results = [
        api.CheckResult(phone_number=n, status=api.CheckStatus.SAFE) for n in numbers
    ]
    manager.complete_job(job_id, results)


def test_background_task_completion(monkeypatch):
    manager = JobManager(DummyRepository())
    monkeypatch.setattr(api, "job_manager", manager)
    monkeypatch.setattr(api, "_new_job", lambda service: "job123")

    async def immediate(job_id, numbers, service):
        await _dummy_run_check(job_id, numbers, service)

    monkeypatch.setattr(api, "enqueue_job", immediate)

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["123"], "service": "kaspersky"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"job_id": "job123"}
    job = manager.get_job("job123")
    assert job["status"] == "completed"
    assert job["results"][0].phone_number == "123"


def test_device_error_response(monkeypatch):
    def failing_ping(host, port, timeout=5):
        raise api.DeviceConnectionError("unreachable")

    monkeypatch.setattr(api, "_ping_device", failing_ping)

    @api.app.get("/ping_test")
    async def ping_test(_: str = api.Depends(api.get_token)):
        api._ping_device("1.2.3.4", "5555")
        return {"ok": True}

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.get("/ping_test", headers=headers)
    assert response.status_code == 503
    assert "unreachable" in response.json()["detail"]


def test_job_failed_when_device_unreachable(monkeypatch):
    def failing_ping(host, port, timeout=5):
        raise api.DeviceConnectionError("boom")

    manager = JobManager(DummyRepository())
    monkeypatch.setattr(api, "job_manager", manager)
    monkeypatch.setattr(api, "_new_job", lambda service: "job123")
    monkeypatch.setattr(api, "_ping_device", failing_ping)

    async def immediate(job_id, numbers, service):
        if service == "getcontact":
            await api._run_check_gc(job_id, numbers)
        else:
            await api._run_check(job_id, numbers, service)

    monkeypatch.setattr(api, "enqueue_job", immediate)

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["123"], "service": "kaspersky"},
        headers=headers,
    )
    assert response.status_code == 200
    job = manager.get_job("job123")
    assert job["status"] == "failed"
    assert "boom" in job["error"]


def test_job_already_running(monkeypatch):
    def busy_new_job(service):
        raise api.JobAlreadyRunningError("Previous task is still in progress")

    monkeypatch.setattr(api, "_new_job", busy_new_job)

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["123"], "service": "kaspersky"},
        headers=headers,
    )
    assert response.status_code == 429
    assert "in progress" in response.json()["detail"]


def test_invalid_phone_number():
    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["abc"], "service": "kaspersky"},
        headers=headers,
    )
    assert response.status_code == 422


def test_multiple_jobs(monkeypatch):
    manager = JobManager(DummyRepository())
    monkeypatch.setattr(api, "job_manager", manager)
    ids = ["job1", "job2"]

    def gen_id(service):
        return ids.pop(0)

    monkeypatch.setattr(api, "_new_job", gen_id)

    async def immediate(job_id, numbers, service):
        await _dummy_run_check(job_id, numbers, service)

    monkeypatch.setattr(api, "enqueue_job", immediate)

    client = TestClient(api.app)
    headers = _auth_header(client)

    r1 = client.post(
        "/check_numbers",
        json={"numbers": ["111"], "service": "kaspersky"},
        headers=headers,
    )
    r2 = client.post(
        "/check_numbers",
        json={"numbers": ["222"], "service": "truecaller"},
        headers=headers,
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert manager.get_job("job1")["status"] == "completed"
    assert manager.get_job("job2")["status"] == "completed"
