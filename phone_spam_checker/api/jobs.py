import asyncio
import contextlib
import logging
import re
import socket
from typing import Any, Dict, List, Optional
from fastapi import FastAPI

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from phone_spam_checker.config import settings
from phone_spam_checker.domain.models import PhoneCheckResult, CheckStatus
from .schemas import CheckResult, ServiceResult
from phone_spam_checker.domain.phone_checker import PhoneChecker
from phone_spam_checker.exceptions import DeviceConnectionError, JobAlreadyRunningError
from phone_spam_checker.job_manager import JobManager
from phone_spam_checker.registry import get_checker_class
from phone_spam_checker.bootstrap import initialize

logger = logging.getLogger(__name__)


async def _check_all(
    checker: PhoneChecker, numbers: List[str]
) -> List[PhoneCheckResult]:
    """Sequentially check all numbers on one device."""
    results: List[PhoneCheckResult] = []
    for num in numbers:
        results.append(await asyncio.to_thread(checker.check_number, num))
    return results


async def enqueue_job(
    job_id: str, numbers: List[str], service: str, app: FastAPI
) -> None:
    """Place a new job into the worker queue."""
    queue = app.state.job_queue
    await queue.put((job_id, numbers, service))


async def _worker(app: FastAPI) -> None:
    job_manager = app.state.job_manager
    queue = app.state.job_queue
    pools = app.state.device_pools
    while True:
        job_id, numbers, service = await queue.get()
        try:
            if service == "kaspersky":
                with pools["kaspersky"] as kasp_dev:
                    await _run_check(
                        job_id,
                        numbers,
                        service,
                        job_manager,
                        kasp_device=kasp_dev,
                    )
            elif service == "truecaller":
                with pools["truecaller"] as tc_dev:
                    await _run_check(
                        job_id,
                        numbers,
                        service,
                        job_manager,
                        tc_device=tc_dev,
                    )
            elif service == "getcontact":
                with pools["getcontact"] as gc_dev:
                    await _run_check_gc(job_id, numbers, job_manager, gc_dev)
            elif service == "tbank":
                await _run_check_tbank(job_id, numbers, job_manager)
            else:  # auto
                needed = _devices_for_service("auto", numbers)
                with contextlib.ExitStack() as stack:
                    kasp_dev = tc_dev = gc_dev = None
                    if "kaspersky" in needed:
                        kasp_dev = stack.enter_context(pools["kaspersky"])
                    if "truecaller" in needed:
                        tc_dev = stack.enter_context(pools["truecaller"])
                    if "getcontact" in needed:
                        gc_dev = stack.enter_context(pools["getcontact"])
                    await _run_check_auto(
                        job_id,
                        numbers,
                        job_manager,
                        kasp_device=kasp_dev,
                        tc_device=tc_dev,
                        gc_device=gc_dev,
                    )
        except JobAlreadyRunningError as exc:
            _fail_job(job_id, str(exc), job_manager)
        except Exception as exc:  # pragma: no cover - unexpected errors
            logger.exception("Worker error for job %s", job_id)
            _fail_job(job_id, str(exc), job_manager)
        finally:
            queue.task_done()


async def cleanup_jobs(app: FastAPI) -> None:
    await app.state.job_manager.cleanup_loop()


async def start_background_tasks(app: FastAPI) -> None:
    initialize()
    asyncio.create_task(cleanup_jobs(app))
    services = ["kaspersky", "truecaller", "getcontact", "tbank"]
    pools = app.state.device_pools
    device_count = sum(len(pools[svc]) for svc in services)
    num_workers = settings.worker_count or device_count
    for _ in range(num_workers):
        asyncio.create_task(_worker(app))


# =============================================================================
# 1. Kaspersky / Truecaller
# =============================================================================
async def _run_check(
    job_id: str,
    numbers: List[str],
    service: str,
    job_manager: JobManager,
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
        kasp_nums = [n for n in numbers if re.match(r"^(?:7|8)\d{10}$", n)]
        tc_nums = [n for n in numbers if n not in kasp_nums]

    # -- ADB device addresses
    kasp_device = kasp_device or f"{settings.kasp_adb_host}:{settings.kasp_adb_port}"
    tc_device = tc_device or f"{settings.tc_adb_host}:{settings.tc_adb_port}"

    kasp_checker = tc_checker = None
    results: List[CheckResult] = []

    try:
        # -- device initialization
        if kasp_nums:
            await asyncio.to_thread(_ping_device, *kasp_device.split(":"))
            kasp_checker_cls = get_checker_class("kaspersky")
            kasp_checker = await asyncio.to_thread(kasp_checker_cls, kasp_device)
            launched = await asyncio.to_thread(kasp_checker.launch_app)
            if not launched:
                raise RuntimeError("Failed to launch Kaspersky Who Calls")

        if tc_nums:
            await asyncio.to_thread(_ping_device, *tc_device.split(":"))
            tc_checker_cls = get_checker_class("truecaller")
            tc_checker = await asyncio.to_thread(tc_checker_cls, tc_device)
            launched = await asyncio.to_thread(tc_checker.launch_app)
            if not launched:
                raise RuntimeError("Failed to launch Truecaller")

        # -- parallel checking
        tasks = []
        if kasp_nums:
            tasks.append(_check_all(kasp_checker, kasp_nums))
        if tc_nums:
            tasks.append(_check_all(tc_checker, tc_nums))

        grouped = await asyncio.gather(*tasks)

        # -- merge results
        merged: Dict[str, Any] = {r.phone_number: r for group in grouped for r in group}
        for num in numbers:
            r = merged.get(num)
            if r:
                results.append(
                    CheckResult(
                        phone_number=r.phone_number,
                        status=r.status,
                        details=r.details,
                        services=[
                            ServiceResult(
                                service=service, status=r.status, details=r.details
                            )
                        ],
                    )
                )
            else:
                results.append(
                    CheckResult(
                        phone_number=num,
                        status=CheckStatus.ERROR,
                        details="No result",
                        services=[
                            ServiceResult(
                                service=service,
                                status=CheckStatus.ERROR,
                                details="No result",
                            )
                        ],
                    )
                )

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e), job_manager)
    else:
        _complete_job(job_id, results, job_manager)
        duration = asyncio.get_event_loop().time() - start_ts
        logger.info("Job %s completed in %.2fs", job_id, duration)
    finally:
        if kasp_checker:
            await asyncio.to_thread(kasp_checker.close_app)
        if tc_checker:
            await asyncio.to_thread(tc_checker.close_app)


# =============================================================================
# 2. GetContact
# =============================================================================
async def _run_check_gc(
    job_id: str,
    numbers: List[str],
    job_manager: JobManager,
    gc_device: Optional[str] = None,
) -> None:
    # GetContact will add '+' itself; remove duplicates
    uniq_numbers = list(dict.fromkeys(numbers))  # preserve order
    gc_device = gc_device or f"{settings.gc_adb_host}:{settings.gc_adb_port}"
    logger.info("Job %s started for %d numbers via getcontact", job_id, len(numbers))
    start_ts = asyncio.get_event_loop().time()
    checker_cls = get_checker_class("getcontact")
    checker: Optional[PhoneChecker] = None
    results: List[CheckResult] = []

    try:
        await asyncio.to_thread(_ping_device, *gc_device.split(":"))
        checker = await asyncio.to_thread(checker_cls, gc_device)
        launched = await asyncio.to_thread(checker.launch_app)
        if not launched:
            raise RuntimeError("Failed to launch GetContact")

        # Checking (CPU-bound -> executor)
        raw: List[PhoneCheckResult] = await _check_all(checker, uniq_numbers)

        for r in raw:
            results.append(
                CheckResult(
                    phone_number=r.phone_number,
                    status=r.status,
                    details=r.details,
                    services=[
                        ServiceResult(
                            service="getcontact", status=r.status, details=r.details
                        )
                    ],
                )
            )

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e), job_manager)
    else:
        _complete_job(job_id, results, job_manager)
        duration = asyncio.get_event_loop().time() - start_ts
        logger.info("Job %s completed in %.2fs", job_id, duration)
    finally:
        if checker:
            await asyncio.to_thread(checker.close_app)


# =============================================================================
# 3. Tbank
# =============================================================================
async def _run_check_tbank(
    job_id: str,
    numbers: List[str],
    job_manager: JobManager,
) -> None:
    logger.info("Job %s started for %d numbers via tbank", job_id, len(numbers))
    start_ts = asyncio.get_event_loop().time()
    checker_cls = get_checker_class("tbank")
    checker: Optional[PhoneChecker] = None
    results: List[CheckResult] = []

    try:
        checker = await asyncio.to_thread(checker_cls, "")
        launched = await asyncio.to_thread(checker.launch_app)
        if not launched:
            raise RuntimeError("Failed to init Tbank checker")

        raw: List[PhoneCheckResult] = await _check_all(checker, numbers)

        for r in raw:
            results.append(
                CheckResult(
                    phone_number=r.phone_number,
                    status=r.status,
                    details=r.details,
                    services=[
                        ServiceResult(
                            service="tbank", status=r.status, details=r.details
                        )
                    ],
                )
            )

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e), job_manager)
    else:
        _complete_job(job_id, results, job_manager)
        duration = asyncio.get_event_loop().time() - start_ts
        logger.info("Job %s completed in %.2fs", job_id, duration)
    finally:
        if checker:
            await asyncio.to_thread(checker.close_app)


# =============================================================================
# 4. Auto mode combining multiple services
# =============================================================================
async def _run_check_auto(
    job_id: str,
    numbers: List[str],
    job_manager: JobManager,
    *,
    kasp_device: Optional[str] = None,
    tc_device: Optional[str] = None,
    gc_device: Optional[str] = None,
) -> None:
    logger.info("Job %s started for %d numbers via auto", job_id, len(numbers))
    start_ts = asyncio.get_event_loop().time()

    kasp_cls = get_checker_class("kaspersky")
    tc_cls = get_checker_class("truecaller")
    gc_cls = get_checker_class("getcontact")
    tb_cls = get_checker_class("tbank")

    kasp_checker = tc_checker = gc_checker = tb_checker = None
    service_map: Dict[str, Dict[str, PhoneCheckResult]] = {n: {} for n in numbers}

    ru_mask = re.compile(r"^(?:\+?7|8)\d{10}$")
    ru_nums_orig = [n for n in numbers if ru_mask.match(n)]
    intl_nums_orig = [n for n in numbers if n not in ru_nums_orig]

    kasp_nums = [n.lstrip("+") for n in ru_nums_orig]
    gc_nums = ru_nums_orig
    tb_nums = [n.lstrip("+") for n in ru_nums_orig]
    tc_nums = [n.lstrip("+") for n in intl_nums_orig]

    try:

        async def run_kaspersky() -> Dict[str, PhoneCheckResult]:
            nonlocal kasp_checker
            res: Dict[str, PhoneCheckResult] = {}
            kasp_device_addr = (
                kasp_device or f"{settings.kasp_adb_host}:{settings.kasp_adb_port}"
            )
            await asyncio.to_thread(_ping_device, *kasp_device_addr.split(":"))
            kasp_checker = await asyncio.to_thread(kasp_cls, kasp_device_addr)
            launched = await asyncio.to_thread(kasp_checker.launch_app)
            if not launched:
                raise RuntimeError("Failed to launch Kaspersky Who Calls")
            raw = await _check_all(kasp_checker, kasp_nums)
            for orig, r in zip(ru_nums_orig, raw):
                res[orig] = r
            return res

        async def run_getcontact() -> Dict[str, PhoneCheckResult]:
            nonlocal gc_checker
            res: Dict[str, PhoneCheckResult] = {}
            gc_device_addr = (
                gc_device or f"{settings.gc_adb_host}:{settings.gc_adb_port}"
            )
            await asyncio.to_thread(_ping_device, *gc_device_addr.split(":"))
            gc_checker = await asyncio.to_thread(gc_cls, gc_device_addr)
            launched = await asyncio.to_thread(gc_checker.launch_app)
            if not launched:
                raise RuntimeError("Failed to launch GetContact")
            raw = await _check_all(gc_checker, gc_nums)
            for orig, r in zip(gc_nums, raw):
                res[orig] = r
            return res

        async def run_tbank() -> Dict[str, PhoneCheckResult]:
            nonlocal tb_checker
            res: Dict[str, PhoneCheckResult] = {}
            tb_checker = await asyncio.to_thread(tb_cls, "")
            launched = await asyncio.to_thread(tb_checker.launch_app)
            if not launched:
                raise RuntimeError("Failed to init Tbank checker")
            raw = await _check_all(tb_checker, tb_nums)
            for orig, r in zip(ru_nums_orig, raw):
                res[orig] = r
            return res

        async def run_truecaller() -> Dict[str, PhoneCheckResult]:
            nonlocal tc_checker
            res: Dict[str, PhoneCheckResult] = {}
            tc_device_addr = (
                tc_device or f"{settings.tc_adb_host}:{settings.tc_adb_port}"
            )
            await asyncio.to_thread(_ping_device, *tc_device_addr.split(":"))
            tc_checker = await asyncio.to_thread(tc_cls, tc_device_addr)
            launched = await asyncio.to_thread(tc_checker.launch_app)
            if not launched:
                raise RuntimeError("Failed to launch Truecaller")
            raw = await _check_all(tc_checker, tc_nums)
            for orig, r in zip(intl_nums_orig, raw):
                res[orig] = r
            return res

        tasks: List[tuple[str, asyncio.Future]] = []
        if kasp_nums:
            tasks.append(("kaspersky", asyncio.create_task(run_kaspersky())))
        if gc_nums:
            tasks.append(("getcontact", asyncio.create_task(run_getcontact())))
        if tb_nums:
            tasks.append(("tbank", asyncio.create_task(run_tbank())))
        if tc_nums:
            tasks.append(("truecaller", asyncio.create_task(run_truecaller())))

        for svc, fut in tasks:
            mapping = await fut
            for orig, r in mapping.items():
                service_map[orig][svc] = r

        def pick_best(phone: str, items: Dict[str, PhoneCheckResult]) -> CheckResult:
            priority = {
                CheckStatus.SPAM: 4,
                CheckStatus.SAFE: 3,
                CheckStatus.NOT_IN_DB: 2,
                CheckStatus.UNKNOWN: 1,
                CheckStatus.ERROR: 0,
            }
            best = None
            for r in items.values():
                if best is None or priority[r.status] > priority[best.status]:
                    best = r
            if not best:
                services = []
            else:
                services = [
                    ServiceResult(service=s, status=res.status, details=res.details)
                    for s, res in items.items()
                ]
            if not best:
                return CheckResult(
                    phone_number=phone,
                    status=CheckStatus.ERROR,
                    details="No result",
                    services=services,
                )
            return CheckResult(
                phone_number=phone,
                status=best.status,
                details=best.details,
                services=services,
            )

        final_results = [pick_best(num, service_map[num]) for num in numbers]

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e), job_manager)
    else:
        _complete_job(job_id, final_results, job_manager)
        duration = asyncio.get_event_loop().time() - start_ts
        logger.info("Job %s completed in %.2fs", job_id, duration)
    finally:
        if kasp_checker:
            await asyncio.to_thread(kasp_checker.close_app)
        if tc_checker:
            await asyncio.to_thread(tc_checker.close_app)
        if gc_checker:
            await asyncio.to_thread(gc_checker.close_app)
        if tb_checker:
            await asyncio.to_thread(tb_checker.close_app)


# Helper functions


def _ping_device(host: str, port: str, timeout: int = 5) -> None:
    logger.debug("Pinging device %s:%s", host, port)
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            logger.debug("Device %s:%s is reachable", host, port)
    except Exception as e:
        logger.error("Device %s:%s unreachable: %s", host, port, e)
        raise DeviceConnectionError(f"Cannot reach device {host}:{port}: {e}") from e


def _devices_for_service(
    service: str, numbers: Optional[List[str]] = None
) -> List[str]:
    if service == "kaspersky":
        return ["kaspersky"]
    if service == "truecaller":
        return ["truecaller"]
    if service == "getcontact":
        return ["getcontact"]
    if service == "tbank":
        return ["tbank"]
    # auto uses kaspersky, getcontact and tbank for Russian numbers;
    # truecaller only if there are international numbers
    if numbers is None:
        return ["kaspersky", "truecaller", "getcontact", "tbank"]

    ru_mask = re.compile(r"^(?:\+?7|8)\d{10}$")
    devs = ["kaspersky", "getcontact", "tbank"]
    if any(not ru_mask.match(n) for n in numbers):
        devs.append("truecaller")
    return devs


def _ensure_no_running(
    service: str, job_manager: JobManager, numbers: Optional[List[str]] = None
) -> None:
    try:
        for dev in _devices_for_service(service, numbers):
            job_manager.ensure_no_running(dev)
    except JobAlreadyRunningError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e


def _new_job(
    service: str, job_manager: JobManager, numbers: Optional[List[str]] = None
) -> str:
    job_id = job_manager.new_job(_devices_for_service(service, numbers))
    logger.debug("Created job %s", job_id)
    return job_id


def _complete_job(
    job_id: str, results: List[CheckResult], job_manager: JobManager
) -> None:
    logger.debug("Marking job %s as completed", job_id)
    job_manager.complete_job(job_id, results)


def _fail_job(job_id: str, error: str, job_manager: JobManager) -> None:
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
