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
    monkeypatch.setattr(api, "job_manager", manager)
    monkeypatch.setattr(api, "get_checker_class", lambda name: DummyChecker)
    monkeypatch.setattr(api, "_ping_device", lambda *a, **kw: None)

    api.device_pools = {
        "kaspersky": DevicePool(["dev1", "dev2"]),
        "truecaller": DevicePool([]),
        "getcontact": DevicePool([]),
    }

    j1 = api._new_job("kaspersky")
    j2 = api._new_job("kaspersky")

    workers = [asyncio.create_task(api._worker()) for _ in range(2)]
    await api.enqueue_job(j1, ["111"], "kaspersky")
    await api.enqueue_job(j2, ["222"], "kaspersky")
    await api.job_queue.join()

    for w in workers:
        w.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(*workers)

    assert manager.get_job(j1)["status"] == "completed"
    assert manager.get_job(j2)["status"] == "completed"
    assert len(api.device_pools["kaspersky"]) == 2

