import sys
import types
import asyncio
import contextlib
import pytest

sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))

from phone_spam_checker.logging_config import configure_logging
from phone_spam_checker.config import settings

configure_logging(level=settings.log_level, fmt=settings.log_format, log_file=settings.log_file)

from phone_spam_checker import api
from phone_spam_checker.job_manager import JobManager, SQLiteJobRepository
from phone_spam_checker.dependencies import get_job_manager, get_device_pool
import phone_spam_checker.dependencies as deps
from phone_spam_checker.domain.models import PhoneCheckResult, CheckStatus
from phone_spam_checker.domain.phone_checker import PhoneChecker
from phone_spam_checker.device_pool import DevicePool


class DummyChecker(PhoneChecker):
    def launch_app(self) -> bool:
        return True

    def close_app(self) -> None:
        pass

    def check_number(self, phone: str) -> PhoneCheckResult:
        return PhoneCheckResult(phone_number=phone, status=CheckStatus.SAFE)


@pytest.mark.asyncio
async def test_parallel_checks(monkeypatch):
    repo = SQLiteJobRepository(":memory:")
    manager = JobManager(repo)
    api.app.dependency_overrides[get_job_manager] = lambda: manager
    monkeypatch.setattr(deps, "get_job_manager", lambda: manager)
    monkeypatch.setattr(api.jobs, "get_job_manager", lambda: manager)
    deps._job_manager = manager
    api.jobs.job_queue = asyncio.Queue()
    deps._job_queue = api.jobs.job_queue
    monkeypatch.setattr(api.jobs, "get_checker_class", lambda name: DummyChecker)
    monkeypatch.setattr(api.jobs, "_ping_device", lambda *a, **kw: None)

    pools = {
        "kaspersky": DevicePool(["dev1", "dev2"]),
        "truecaller": DevicePool([]),
        "getcontact": DevicePool([]),
    }
    monkeypatch.setattr(deps, "get_device_pool", lambda service: pools[service])
    monkeypatch.setattr(api.jobs, "get_device_pool", lambda service: pools[service])

    j1 = api.jobs._new_job("kaspersky", manager)
    j2 = api.jobs._new_job("kaspersky", manager)

    workers = [asyncio.create_task(api.jobs._worker()) for _ in range(2)]
    await api.jobs.enqueue_job(j1, ["111"], "kaspersky")
    await api.jobs.enqueue_job(j2, ["222"], "kaspersky")
    await api.jobs.job_queue.join()

    for w in workers:
        w.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(*workers)

    assert manager.get_job(j1)["status"] == "completed"
    assert manager.get_job(j2)["status"] == "completed"
    assert len(pools["kaspersky"]) == 2
    api.app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_worker_recovers_on_error(monkeypatch):
    repo = SQLiteJobRepository(":memory:")
    manager = JobManager(repo)
    api.app.dependency_overrides[get_job_manager] = lambda: manager
    monkeypatch.setattr(deps, "get_job_manager", lambda: manager)
    monkeypatch.setattr(api.jobs, "get_job_manager", lambda: manager)
    deps._job_manager = manager
    api.jobs.job_queue = asyncio.Queue()
    deps._job_queue = api.jobs.job_queue
    monkeypatch.setattr(api.jobs, "get_checker_class", lambda name: DummyChecker)
    monkeypatch.setattr(api.jobs, "_ping_device", lambda *a, **kw: None)

    pools = {
        "kaspersky": DevicePool(["dev1"]),
        "truecaller": DevicePool([]),
        "getcontact": DevicePool([]),
    }

    counter = {"n": 0}

    def faulty_pool(service: str):
        if counter["n"] == 0:
            counter["n"] += 1
            raise RuntimeError("boom")
        return pools[service]

    monkeypatch.setattr(deps, "get_device_pool", faulty_pool)
    monkeypatch.setattr(api.jobs, "get_device_pool", faulty_pool)

    j1 = api.jobs._new_job("kaspersky", manager)
    j2 = api.jobs._new_job("kaspersky", manager)

    worker = asyncio.create_task(api.jobs._worker())
    await api.jobs.enqueue_job(j1, ["111"], "kaspersky")
    await api.jobs.enqueue_job(j2, ["222"], "kaspersky")
    await api.jobs.job_queue.join()

    worker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker

    assert manager.get_job(j1)["status"] == "failed"
    assert manager.get_job(j2)["status"] == "completed"
    assert len(pools["kaspersky"]) == 1
    api.app.dependency_overrides.clear()

