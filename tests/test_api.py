import asyncio
from datetime import datetime
import jwt

import pytest
from fastapi.testclient import TestClient
from fastapi import Depends, Request

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
from phone_spam_checker.job_manager import JobRepository, JobManager, SQLiteJobRepository
from phone_spam_checker.dependencies import get_job_manager
import phone_spam_checker.dependencies as deps
from phone_spam_checker.exceptions import JobAlreadyRunningError, DeviceConnectionError
from phone_spam_checker.device_pool import DevicePool
from phone_spam_checker.domain.phone_checker import PhoneChecker
from phone_spam_checker.domain.models import PhoneCheckResult, CheckStatus

configure_logging(
    level=settings.log_level,
    fmt=settings.log_format,
    log_file=settings.log_file,
)

from phone_spam_checker import api


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
    resp = client.post("/login", headers={"X-API-Key": settings.api_key})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_submit_check(monkeypatch):
    def override(request: Request):
        return JobManager(DummyRepository())

    api.app.dependency_overrides[get_job_manager] = override
    monkeypatch.setattr(api.jobs, "_new_job", lambda service, jm: "job123")
    called = {}

    async def fake_enqueue(job_id, numbers, service, app):
        called["task"] = (job_id, numbers, service)

    monkeypatch.setattr(api.jobs, "enqueue_job", fake_enqueue)

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["123"], "service": "getcontact"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"job_id": "job123"}
    api.app.dependency_overrides.clear()


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
    def override(request: Request):
        return JobManager(DummyRepository(job_data))

    api.app.dependency_overrides[get_job_manager] = override

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
    api.app.dependency_overrides.clear()


async def _dummy_run_check(job_id, numbers, service, manager):
    results = [
        api.CheckResult(phone_number=n, status=api.CheckStatus.SAFE) for n in numbers
    ]
    manager.complete_job(job_id, results)


def test_background_task_completion(monkeypatch):
    manager = JobManager(DummyRepository())
    api.app.state.job_manager = manager
    def override(request: Request):
        return manager

    api.app.dependency_overrides[get_job_manager] = override
    monkeypatch.setattr(api.jobs, "_new_job", lambda service, jm: "job123")

    async def immediate(job_id, numbers, service, app):
        await _dummy_run_check(job_id, numbers, service, manager)

    monkeypatch.setattr(api.jobs, "enqueue_job", immediate)

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
    api.app.dependency_overrides.clear()


def test_device_error_response(monkeypatch):
    def failing_ping(host, port, timeout=5):
        raise DeviceConnectionError("unreachable")

    monkeypatch.setattr(api.jobs, "_ping_device", failing_ping)

    @api.app.get("/ping_test")
    async def ping_test(_: str = Depends(api.auth.get_token)):
        api.jobs._ping_device("1.2.3.4", "5555")
        return {"ok": True}

    client = TestClient(api.app)
    headers = _auth_header(client)
    response = client.get("/ping_test", headers=headers)
    assert response.status_code == 503
    assert "unreachable" in response.json()["detail"]


def test_job_failed_when_device_unreachable(monkeypatch):
    def failing_ping(host, port, timeout=5):
        raise DeviceConnectionError("boom")

    manager = JobManager(DummyRepository())
    api.app.state.job_manager = manager
    def override(request: Request):
        return manager

    api.app.dependency_overrides[get_job_manager] = override
    monkeypatch.setattr(api.jobs, "_new_job", lambda service, jm: "job123")
    monkeypatch.setattr(api.jobs, "_ping_device", failing_ping)

    async def immediate(job_id, numbers, service, app):
        if service == "getcontact":
            await api.jobs._run_check_gc(job_id, numbers, manager)
        else:
            await api.jobs._run_check(job_id, numbers, service, manager)

    monkeypatch.setattr(api.jobs, "enqueue_job", immediate)

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
    api.app.dependency_overrides.clear()


def test_job_already_running(monkeypatch):
    def busy_new_job(service, jm):
        raise JobAlreadyRunningError("Previous task is still in progress")

    monkeypatch.setattr(api.jobs, "_new_job", busy_new_job)

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
    api.app.state.job_manager = manager
    def override(request: Request):
        return manager

    api.app.dependency_overrides[get_job_manager] = override
    ids = ["job1", "job2"]

    def gen_id(service):
        return ids.pop(0)

    monkeypatch.setattr(api.jobs, "_new_job", lambda service, jm: gen_id(service))

    async def immediate(job_id, numbers, service, app):
        await _dummy_run_check(job_id, numbers, service, manager)

    monkeypatch.setattr(api.jobs, "enqueue_job", immediate)

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
    api.app.dependency_overrides.clear()


def test_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "token_ttl_hours", -1)
    def override(request: Request):
        return JobManager(DummyRepository())

    api.app.dependency_overrides[get_job_manager] = override
    client = TestClient(api.app)
    resp = client.post("/login", headers={"X-API-Key": settings.api_key})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/status/job123", headers=headers)
    assert r.status_code == 403
    api.app.dependency_overrides.clear()
    monkeypatch.setattr(settings, "token_ttl_hours", 1)


def test_token_contains_claims():
    client = TestClient(api.app)
    resp = client.post("/login", headers={"X-API-Key": settings.api_key})
    token = resp.json()["access_token"]
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=["HS256"],
        audience=settings.token_audience,
        issuer=settings.token_issuer,
    )
    assert payload["aud"] == settings.token_audience
    assert payload["iss"] == settings.token_issuer
    assert payload["sub"] == "api"


@pytest.mark.asyncio
async def test_auto_returns_service_results(monkeypatch):
    repo = SQLiteJobRepository(":memory:")
    manager = JobManager(repo)
    api.app.state.job_manager = manager
    api.app.state.job_queue = asyncio.Queue()

    class DummyChecker(PhoneChecker):
        def __init__(self, device: str, svc: str) -> None:
            super().__init__(device)
            self.svc = svc

        def launch_app(self) -> bool:
            return True

        def close_app(self) -> None:
            pass

        def check_number(self, phone: str) -> PhoneCheckResult:
            mapping = {
                "kaspersky": CheckStatus.SAFE,
                "getcontact": CheckStatus.NOT_IN_DB,
                "tbank": CheckStatus.SPAM,
                "truecaller": CheckStatus.SAFE,
            }
            return PhoneCheckResult(phone_number=phone, status=mapping[self.svc])

    def get_cls(name: str):
        return lambda device: DummyChecker(device, name)

    monkeypatch.setattr(api.jobs, "get_checker_class", get_cls)
    monkeypatch.setattr(api.jobs, "_ping_device", lambda *a, **kw: None)

    pools = {
        "kaspersky": DevicePool(["d1"]),
        "truecaller": DevicePool(["d2"]),
        "getcontact": DevicePool(["d3"]),
        "tbank": DevicePool([]),
    }
    api.app.state.device_pools = pools

    job_id = api.jobs._new_job("auto", manager)
    await api.jobs._run_check_auto(job_id, ["79100000000", "+123"], manager)
    res = manager.get_job(job_id)["results"]
    assert res[0]["services"]
    svcs = {s["service"] for s in res[0]["services"]}
    assert svcs == {"kaspersky", "getcontact", "tbank"}
    assert res[1]["services"][0]["service"] == "truecaller"


@pytest.mark.asyncio
async def test_auto_russian_with_8(monkeypatch):
    repo = SQLiteJobRepository(":memory:")
    manager = JobManager(repo)
    api.app.state.job_manager = manager
    api.app.state.job_queue = asyncio.Queue()

    called: list[str] = []

    class DummyChecker(PhoneChecker):
        def __init__(self, device: str, svc: str) -> None:
            super().__init__(device)
            self.svc = svc

        def launch_app(self) -> bool:
            return True

        def close_app(self) -> None:
            pass

        def check_number(self, phone: str) -> PhoneCheckResult:
            called.append(self.svc)
            return PhoneCheckResult(phone_number=phone, status=CheckStatus.SAFE)

    def get_cls(name: str):
        return lambda device: DummyChecker(device, name)

    monkeypatch.setattr(api.jobs, "get_checker_class", get_cls)
    monkeypatch.setattr(api.jobs, "_ping_device", lambda *a, **kw: None)

    pools = {
        "kaspersky": DevicePool(["d1"]),
        "truecaller": DevicePool(["d2"]),
        "getcontact": DevicePool(["d3"]),
        "tbank": DevicePool([]),
    }
    api.app.state.device_pools = pools

    job_id = api.jobs._new_job("auto", manager)
    await api.jobs._run_check_auto(job_id, ["89260000000"], manager)
    assert "truecaller" not in called
    res = manager.get_job(job_id)["results"][0]["services"]
    svcs = {s["service"] for s in res}
    assert svcs == {"kaspersky", "getcontact", "tbank"}


def test_new_job_records_tbank():
    captured = {}

    class CaptureRepo(DummyRepository):
        def new_job(self, devices):
            captured["devices"] = devices
            return super().new_job(devices)

    manager = JobManager(CaptureRepo())
    job_id = api.jobs._new_job("auto", manager)
    assert job_id == "job123"
    assert "tbank" in captured["devices"]


def test_db_stores_unicode():
    repo = SQLiteJobRepository(":memory:")
    manager = JobManager(repo)

    result = api.CheckResult(
        phone_number="123",
        status=api.CheckStatus.SPAM,
        details="Русский текст"
    )

    job_id = manager.new_job([])
    manager.complete_job(job_id, [result])

    stored = repo._db.execute("SELECT results FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0]
    assert "Русский текст" in stored


def test_tbank_decodes_escaped_html(monkeypatch):
    import requests as req

    escaped = (
        "<div>\u041d\u043e\u043c\u0435\u0440 8"  # 'Номер 8'
        "\u0432\u0435\u0440\u043e\u044f\u0442\u043d\u043e, "
        "\u043f\u0440\u0438\u043d\u0430\u0434\u043b\u0435\u0436\u0438\u0442 "
        "\u0441\u043f\u0430\u043c\u0435\u0440\u0443</div>"
    )

    class DummyResp:
        def __init__(self, text: str) -> None:
            self.text = text

    monkeypatch.setattr(req, "get", lambda *a, **kw: DummyResp(escaped))

    from phone_spam_checker.infrastructure import TbankChecker

    checker = TbankChecker("")
    res = checker.check_number("89100000000")
    assert res.status != api.CheckStatus.UNKNOWN


def test_tbank_decodes_mojibake(monkeypatch):
    import requests as req

    html = "<div>Номер 8 вероятно, принадлежит спамеру</div>".encode("utf-8")

    class DummyResp:
        def __init__(self, content: bytes) -> None:
            self.content = content
            # emulate wrong decoding to latin1 by requests
            self.text = content.decode("latin1")
            self.encoding = None

    monkeypatch.setattr(req, "get", lambda *a, **kw: DummyResp(html))

    from phone_spam_checker.infrastructure import TbankChecker

    checker = TbankChecker("")
    res = checker.check_number("89100000000")
    assert res.status == api.CheckStatus.SPAM
