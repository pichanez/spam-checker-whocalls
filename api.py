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
import threading
import asyncio
import re
import socket
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

# --- checker imports ----------------------------------------------------------
from phone_spam_checker.infrastructure import (
    KasperskyWhoCallsChecker,
    TruecallerChecker,
    GetContactChecker,
)
from phone_spam_checker.domain.models import PhoneCheckResult

# --- API key authorization ----------------------------------------------------
API_KEY = os.getenv("API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key


# --- background parameters ----------------------------------------------------
CLEANUP_INTERVAL_SECONDS = 60
JOB_TTL = timedelta(hours=1)
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()

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

# --- cleanup old jobs --------------------------------------------------------
async def cleanup_jobs() -> None:
    while True:
        now = datetime.utcnow()
        with jobs_lock:
            outdated = [
                jid
                for jid, info in jobs.items()
                if now - info.get("created_at", now) > JOB_TTL
            ]
            for jid in outdated:
                del jobs[jid]
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


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
            kasp_checker = KasperskyWhoCallsChecker(kasp_device)
            if not kasp_checker.launch_app():
                raise RuntimeError("Failed to launch Kaspersky Who Calls")

        if tc_nums:
            _ping_device(*tc_device.split(":"))
            tc_checker = TruecallerChecker(tc_device)
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
    checker: Optional[GetContactChecker] = None
    results: List[CheckResult] = []
    loop = asyncio.get_event_loop()

    try:
        _ping_device(*gc_device.split(":"))
        checker = GetContactChecker(gc_device)
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
    with jobs_lock:
        job = jobs.get(job_id)
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
    with jobs_lock:
        if any(info.get("status") == "in_progress" for info in jobs.values()):
            raise HTTPException(status_code=429, detail="Previous task is still in progress")


def _new_job() -> str:
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "status": "in_progress",
            "results": None,
            "error": None,
            "created_at": datetime.utcnow(),
        }
    return job_id


def _complete_job(job_id: str, results: List[CheckResult]) -> None:
    with jobs_lock:
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["results"] = results


def _fail_job(job_id: str, error: str) -> None:
    with jobs_lock:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = error