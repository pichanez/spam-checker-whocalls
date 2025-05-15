#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

# Импорты чекеров
from kaspersky_phone_checker import KasperskyWhoCallsChecker, PhoneCheckResult as KasperskyResult
from truecaller_phone_checker import TruecallerChecker, PhoneCheckResult as TruecallerResult

# Загрузка API-ключа
API_KEY = os.getenv("API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key

# Параметры очистки задач
CLEANUP_INTERVAL_SECONDS = 60
JOB_TTL = timedelta(hours=1)

# Хранилище задач
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()

# Pydantic-модели
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

# Инициализация FastAPI
app = FastAPI(title="Phone Checker API", version="1.0", dependencies=[Depends(get_api_key)])

# Фоновая очистка старых задач
async def cleanup_jobs():
    while True:
        now = datetime.utcnow()
        with jobs_lock:
            to_delete = [jid for jid, info in jobs.items()
                         if info.get("created_at") and now - info["created_at"] > JOB_TTL]
            for jid in to_delete:
                del jobs[jid]
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

@app.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_jobs())

async def _run_check(job_id: str, numbers: List[str]):
    # Нормализуем номера: убираем '+' если есть
    numbers = [num.lstrip('+') for num in numbers]

    # Определяем группы номеров
    kasp_nums = [num for num in numbers if re.match(r"^(7|\\+7)9.*", num)]
    tc_nums   = [num for num in numbers if not re.match(r"^(7|\\+7)9.*", num)]

    # Адреса ADB-устройств
    kasp_host = os.getenv("KASP_ADB_HOST", "127.0.0.1")
    kasp_port = int(os.getenv("KASP_ADB_PORT", "5555"))
    tc_host   = os.getenv("TC_ADB_HOST",   "127.0.0.1")
    tc_port   = int(os.getenv("TC_ADB_PORT",   "5556"))
    kasp_device = f"{kasp_host}:{kasp_port}"
    tc_device   = f"{tc_host}:{tc_port}"

    kasp_checker = None
    tc_checker = None
    results: List[CheckResult] = []

    try:
        # Проверка доступности и запуск приложений
        if kasp_nums:
            try:
                with socket.create_connection((kasp_host, kasp_port), timeout=5): pass
            except Exception as e:
                raise RuntimeError(f"Cannot reach Kaspersky device {kasp_device}: {e}")
            kasp_checker = KasperskyWhoCallsChecker(kasp_device)
            if not kasp_checker.launch_app():
                raise RuntimeError(f"Failed to launch Kaspersky Who Calls on {kasp_device}")

        if tc_nums:
            try:
                with socket.create_connection((tc_host, tc_port), timeout=5): pass
            except Exception as e:
                raise RuntimeError(f"Cannot reach Truecaller device {tc_device}: {e}")
            tc_checker = TruecallerChecker(tc_device)
            if not tc_checker.launch_app():
                raise RuntimeError(f"Failed to launch Truecaller on {tc_device}")

        loop = asyncio.get_event_loop()
        # Функции для групповой обработки
        def process_kasp():
            return [kasp_checker.check_number(num) for num in kasp_nums]
        def process_tc():
            return [tc_checker.check_number(num) for num in tc_nums]

        # Запускаем обе группы параллельно
        tasks = []
        if kasp_nums:
            tasks.append(loop.run_in_executor(None, process_kasp))
        if tc_nums:
            tasks.append(loop.run_in_executor(None, process_tc))
        grouped = await asyncio.gather(*tasks)

        # Собираем результаты по оригинальному порядку
        # grouped: [list[KasperskyResult], list[TruecallerResult]]
        merged: Dict[str, Any] = {}
        for group in grouped:
            for r in group:
                merged[r.phone_number] = r
        for num in numbers:
            res = merged.get(num)
            if res:
                results.append(CheckResult(
                    phone_number=res.phone_number,
                    status=res.status,
                    details=res.details
                ))
            else:
                results.append(CheckResult(
                    phone_number=num,
                    status="Error",
                    details="No result returned"
                ))

        # Закрываем приложения
        if kasp_checker:
            await loop.run_in_executor(None, kasp_checker.close_app)
        if tc_checker:
            await loop.run_in_executor(None, tc_checker.close_app)

        # Сохраняем статус
        with jobs_lock:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["results"] = results
    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)

@app.post("/check_numbers", response_model=JobResponse)
def submit_check(request: CheckRequest, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)) -> JobResponse:
    with jobs_lock:
        if any(info.get("status") == "in_progress" for info in jobs.values()):
            raise HTTPException(status_code=429, detail="Previous task is still in progress")
        job_id = uuid.uuid4().hex
        jobs[job_id] = {"status": "in_progress", "results": None, "error": None, "created_at": datetime.utcnow()}
    background_tasks.add_task(_run_check, job_id, request.numbers)
    return JobResponse(job_id=job_id)

@app.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str, api_key: str = Depends(get_api_key)) -> StatusResponse:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return StatusResponse(job_id=job_id, status=job["status"], results=job.get("results"), error=job.get("error"))
