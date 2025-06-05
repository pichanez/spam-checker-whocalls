import asyncio
import contextlib
import logging
import re
import socket
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from phone_spam_checker.config import settings
from phone_spam_checker.device_pool import DevicePool
from phone_spam_checker.domain.models import PhoneCheckResult, CheckStatus
from .schemas import CheckResult
from phone_spam_checker.domain.phone_checker import PhoneChecker
from phone_spam_checker.exceptions import DeviceConnectionError, JobAlreadyRunningError
from phone_spam_checker.job_manager import (
    JobManager,
    SQLiteJobRepository,
    PostgresJobRepository,
)
from phone_spam_checker.logging_config import configure_logging
from phone_spam_checker.registry import (
    get_checker_class,
    register_default_checkers,
    load_checker_module,
)

configure_logging(level=settings.log_level, fmt=settings.log_format, log_file=settings.log_file)
register_default_checkers()
for mod in filter(None, getattr(settings, "checker_modules", [])):
    load_checker_module(mod)
logger = logging.getLogger(__name__)

if settings.pg_host:
    job_repo = PostgresJobRepository(settings.pg_dsn)
else:
    job_repo = SQLiteJobRepository(settings.job_db_path)
job_manager = JobManager(job_repo)

job_queue: asyncio.Queue[tuple[str, List[str], str]] = asyncio.Queue()

# device pools will be created on startup
device_pools: Dict[str, DevicePool] = {}


async def enqueue_job(job_id: str, numbers: List[str], service: str) -> None:
    """Place a new job into the worker queue."""
    await job_queue.put((job_id, numbers, service))


async def _worker() -> None:
    while True:
        job_id, numbers, service = await job_queue.get()
        try:
            if service == "getcontact":
                with device_pools["getcontact"] as gc_dev:
                    await _run_check_gc(job_id, numbers, gc_dev)
            else:
                with contextlib.ExitStack() as stack:
                    kasp_dev = tc_dev = None
                    if service in {"kaspersky", "auto"}:
                        kasp_dev = stack.enter_context(device_pools["kaspersky"])
                    if service in {"truecaller", "auto"}:
                        tc_dev = stack.enter_context(device_pools["truecaller"])
                    await _run_check(
                        job_id,
                        numbers,
                        service,
                        kasp_device=kasp_dev,
                        tc_device=tc_dev,
                    )
        except JobAlreadyRunningError as exc:
            _fail_job(job_id, str(exc))
        finally:
            job_queue.task_done()


async def cleanup_jobs() -> None:
    await job_manager.cleanup_loop()


async def start_background_tasks() -> None:
    asyncio.create_task(cleanup_jobs())
    device_pools.update(
        {
            "kaspersky": DevicePool(settings.kasp_devices),
            "truecaller": DevicePool(settings.tc_devices),
            "getcontact": DevicePool(settings.gc_devices),
        }
    )
    device_count = sum(len(pool) for pool in device_pools.values())
    num_workers = settings.worker_count or device_count
    for _ in range(num_workers):
        asyncio.create_task(_worker())


# =============================================================================
# 1. Kaspersky / Truecaller
# =============================================================================
async def _run_check(
    job_id: str,
    numbers: List[str],
    service: str,
    *,
    kasp_device: Optional[str] = None,
    tc_device: Optional[str] = None,
) -> None:
    numbers = [num.lstrip("+") for num in numbers]
    logger.info("Job %s started for %d numbers via %s", job_id, len(numbers), service)
    start_ts = asyncio.get_event_loop().time()

    if service == "kaspersky":
        kasp_nums = numbers
        tc_nums = []
    elif service == "truecaller":
        kasp_nums = []
        tc_nums = numbers
    else:  # auto
        kasp_nums = [n for n in numbers if re.match(r"^(7|\+7)9", n)]
        tc_nums = [n for n in numbers if n not in kasp_nums]

    # -- ADB device addresses
    kasp_device = kasp_device or f"{settings.kasp_adb_host}:{settings.kasp_adb_port}"
    tc_device = tc_device or f"{settings.tc_adb_host}:{settings.tc_adb_port}"

    kasp_checker = tc_checker = None
    results: List[CheckResult] = []
    loop = asyncio.get_event_loop()

    try:
        # -- device initialization
        if kasp_nums:
            _ping_device(*kasp_device.split(":"))
            kasp_checker_cls = get_checker_class("kaspersky")
            kasp_checker = kasp_checker_cls(kasp_device)
            if not kasp_checker.launch_app():
                raise RuntimeError("Failed to launch Kaspersky Who Calls")

        if tc_nums:
            _ping_device(*tc_device.split(":"))
            tc_checker_cls = get_checker_class("truecaller")
            tc_checker = tc_checker_cls(tc_device)
            if not tc_checker.launch_app():
                raise RuntimeError("Failed to launch Truecaller")

        # -- parallel checking
        tasks = []
        if kasp_nums:
            tasks.append(
                loop.run_in_executor(
                    None, lambda: [kasp_checker.check_number(n) for n in kasp_nums]
                )
            )
        if tc_nums:
            tasks.append(
                loop.run_in_executor(
                    None, lambda: [tc_checker.check_number(n) for n in tc_nums]
                )
            )

        grouped = await asyncio.gather(*tasks)

        # -- merge results
        merged: Dict[str, Any] = {r.phone_number: r for group in grouped for r in group}
        for num in numbers:
            r = merged.get(num)
            if r:
                results.append(
                    CheckResult(
                        phone_number=r.phone_number, status=r.status, details=r.details
                    )
                )
            else:
                results.append(
                    CheckResult(
                        phone_number=num, status=CheckStatus.ERROR, details="No result"
                    )
                )

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e))
    else:
        _complete_job(job_id, results)
        duration = asyncio.get_event_loop().time() - start_ts
        logger.info("Job %s completed in %.2fs", job_id, duration)
    finally:
        if kasp_checker:
            await loop.run_in_executor(None, kasp_checker.close_app)
        if tc_checker:
            await loop.run_in_executor(None, tc_checker.close_app)


# =============================================================================
# 2. GetContact
# =============================================================================
async def _run_check_gc(
    job_id: str, numbers: List[str], gc_device: Optional[str] = None
) -> None:
    # GetContact will add '+' itself; remove duplicates
    uniq_numbers = list(dict.fromkeys(numbers))  # preserve order
    gc_device = gc_device or f"{settings.gc_adb_host}:{settings.gc_adb_port}"
    logger.info("Job %s started for %d numbers via getcontact", job_id, len(numbers))
    start_ts = asyncio.get_event_loop().time()
    checker_cls = get_checker_class("getcontact")
    checker: Optional[PhoneChecker] = None
    results: List[CheckResult] = []
    loop = asyncio.get_event_loop()

    try:
        _ping_device(*gc_device.split(":"))
        checker = checker_cls(gc_device)
        if not checker.launch_app():
            raise RuntimeError("Failed to launch GetContact")

        # Checking (CPU-bound -> executor)
        raw: List[PhoneCheckResult] = await loop.run_in_executor(
            None, lambda: [checker.check_number(n) for n in uniq_numbers]
        )

        for r in raw:
            results.append(
                CheckResult(
                    phone_number=r.phone_number, status=r.status, details=r.details
                )
            )

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e))
    else:
        _complete_job(job_id, results)
        duration = asyncio.get_event_loop().time() - start_ts
        logger.info("Job %s completed in %.2fs", job_id, duration)
    finally:
        if checker:
            await loop.run_in_executor(None, checker.close_app)


# Helper functions

def _ping_device(host: str, port: str, timeout: int = 5) -> None:
    logger.debug("Pinging device %s:%s", host, port)
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            logger.debug("Device %s:%s is reachable", host, port)
    except Exception as e:
        logger.error("Device %s:%s unreachable: %s", host, port, e)
        raise DeviceConnectionError(f"Cannot reach device {host}:{port}: {e}") from e


def _devices_for_service(service: str) -> List[str]:
    if service == "kaspersky":
        return ["kaspersky"]
    if service == "truecaller":
        return ["truecaller"]
    if service == "getcontact":
        return ["getcontact"]
    # auto uses kaspersky and truecaller devices
    return ["kaspersky", "truecaller"]


def _ensure_no_running(service: str) -> None:
    try:
        for dev in _devices_for_service(service):
            job_manager.ensure_no_running(dev)
    except JobAlreadyRunningError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e


def _new_job(service: str) -> str:
    job_id = job_manager.new_job(_devices_for_service(service))
    logger.debug("Created job %s", job_id)
    return job_id


def _complete_job(job_id: str, results: List[CheckResult]) -> None:
    logger.debug("Marking job %s as completed", job_id)
    job_manager.complete_job(job_id, results)


def _fail_job(job_id: str, error: str) -> None:
    logger.debug("Marking job %s as failed: %s", job_id, error)
    job_manager.fail_job(job_id, error)


def device_error_handler(request, exc: DeviceConnectionError):
    logger.error("Device connection error: %s", exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


async def exception_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
