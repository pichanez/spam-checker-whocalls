#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phone Checker API — Kaspersky / Truecaller / GetContact

Run:
    export API_KEY=supersecret
    uvicorn phone_checker_api:app --host 0.0.0.0 --port 8000
"""

import os
import uuid
import asyncio
import re
import socket
from typing import List, Dict, Optional, Any

import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from phone_spam_checker.job_manager import JobManager
from phone_spam_checker.logging_config import configure_logging

# --- checker imports ----------------------------------------------------------
from phone_spam_checker.registry import get_checker_class
from phone_spam_checker.domain.models import PhoneCheckResult
from phone_spam_checker.domain.phone_checker import PhoneChecker

# --- API key authorization ----------------------------------------------------
API_KEY = os.getenv("API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key


configure_logging()
logger = logging.getLogger(__name__)

job_manager = JobManager()

# --- data models (pydantic) ---------------------------------------------------
class CheckRequest(BaseModel):
    numbers: List[str]


class JobResponse(BaseModel):
    job_id: str


class CheckResult(BaseModel):
    phone_number: str
    status: str
    details: str = ""


class StatusResponse(BaseModel):
    job_id: str
    status: str
    results: Optional[List[CheckResult]] = None
    error: Optional[str] = None


# --- FastAPI ------------------------------------------------------------------
app = FastAPI(
    title="Phone Checker API",
    version="2.0",
    dependencies=[Depends(get_api_key)],
)


@app.middleware("http")
async def exception_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception")
        raise HTTPException(status_code=500, detail="Internal server error") from exc

# --- cleanup old jobs --------------------------------------------------------
async def cleanup_jobs() -> None:
    await job_manager.cleanup_loop()


@app.on_event("startup")
async def start_cleanup_task() -> None:
    asyncio.create_task(cleanup_jobs())


# ═════════════════════════════════════════════════════════════════════════════
# 1. Kaspersky + Truecaller  (legacy endpoint) ---------------------------------
# ═════════════════════════════════════════════════════════════════════════════
async def _run_check(job_id: str, numbers: List[str]) -> None:
    numbers = [num.lstrip("+") for num in numbers]

    # distribute numbers between checkers
    kasp_nums = [n for n in numbers if re.match(r"^(7|\+7)9", n)]
    tc_nums = [n for n in numbers if n not in kasp_nums]

    # -- ADB device addresses --------------------------------------------
    kasp_device = f"{os.getenv('KASP_ADB_HOST', '127.0.0.1')}:{os.getenv('KASP_ADB_PORT', '5555')}"
    tc_device = f"{os.getenv('TC_ADB_HOST', '127.0.0.1')}:{os.getenv('TC_ADB_PORT', '5556')}"

    kasp_checker = tc_checker = None
    results: List[CheckResult] = []
    loop = asyncio.get_event_loop()

    try:
        # -- device initialization --------------------------------------
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

        # -- parallel checking -------------------------------------------
        tasks = []
        if kasp_nums:
            tasks.append(loop.run_in_executor(None, lambda: [kasp_checker.check_number(n) for n in kasp_nums]))
        if tc_nums:
            tasks.append(loop.run_in_executor(None, lambda: [tc_checker.check_number(n) for n in tc_nums]))

        grouped = await asyncio.gather(*tasks)

        # -- merge results ---------------------------------------------------
        merged: Dict[str, Any] = {r.phone_number: r for group in grouped for r in group}
        for num in numbers:
            r = merged.get(num)
            if r:
                results.append(CheckResult(phone_number=r.phone_number, status=r.status, details=r.details))
            else:
                results.append(CheckResult(phone_number=num, status="Error", details="No result"))

    except Exception as e:
        _fail_job(job_id, str(e))
    else:
        _complete_job(job_id, results)
    finally:
        if kasp_checker:
            await loop.run_in_executor(None, kasp_checker.close_app)
        if tc_checker:
            await loop.run_in_executor(None, tc_checker.close_app)


# ═════════════════════════════════════════════════════════════════════════════
# 2. GetContact  (new endpoint) -----------------------------------------------
# ═════════════════════════════════════════════════════════════════════════════
async def _run_check_gc(job_id: str, numbers: List[str]) -> None:
    # GetContact will add '+' itself; remove duplicates
    uniq_numbers = list(dict.fromkeys(numbers))  # preserve order
    gc_device = f"{os.getenv('GC_ADB_HOST', '127.0.0.1')}:{os.getenv('GC_ADB_PORT', '5557')}"
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
                CheckResult(phone_number=r.phone_number, status=r.status, details=r.details)
            )

    except Exception as e:
        _fail_job(job_id, str(e))
    else:
        _complete_job(job_id, results)
    finally:
        if checker:
            await loop.run_in_executor(None, checker.close_app)


# --- endpoints ---------------------------------------------------------------
@app.post("/check_numbers", response_model=JobResponse)
def submit_check(
    request: CheckRequest, background_tasks: BackgroundTasks, _: str = Depends(get_api_key)
) -> JobResponse:
    _ensure_no_running()
    job_id = _new_job()
    background_tasks.add_task(_run_check, job_id, request.numbers)
    return JobResponse(job_id=job_id)


@app.post("/check_numbers_gc", response_model=JobResponse)         # NEW
def submit_check_gc(
    request: CheckRequest, background_tasks: BackgroundTasks, _: str = Depends(get_api_key)
) -> JobResponse:
    _ensure_no_running()
    job_id = _new_job()
    background_tasks.add_task(_run_check_gc, job_id, request.numbers)
    return JobResponse(job_id=job_id)


@app.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str, _: str = Depends(get_api_key)) -> StatusResponse:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        results=job.get("results"),
        error=job.get("error"),
    )


# --- helper functions --------------------------------------------------------
def _ping_device(host: str, port: str, timeout: int = 5) -> None:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            pass
    except Exception as e:
        raise RuntimeError(f"Cannot reach device {host}:{port}: {e}") from e


def _ensure_no_running() -> None:
    job_manager.ensure_no_running()


def _new_job() -> str:
    return job_manager.new_job()


def _complete_job(job_id: str, results: List[CheckResult]) -> None:
    job_manager.complete_job(job_id, results)


def _fail_job(job_id: str, error: str) -> None:
    job_manager.fail_job(job_id, error)
