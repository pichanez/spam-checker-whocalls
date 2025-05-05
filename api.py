import os
import uuid
import threading
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

# Импорт вашего чекера
from kaspersky_phone_checker import KasperskyWhoCallsChecker, PhoneCheckResult

# Загрузка API-ключа из окружения
API_KEY = os.getenv("API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(
    api_key: str = Security(api_key_header)
) -> str:
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key

# Параметры TTL для задач
CLEANUP_INTERVAL_SECONDS = 60        # интервал очистки
JOB_TTL = timedelta(hours=1)         # время жизни задачи

# Структура для хранения задач: status, results, error, created_at
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()

# Модели данных
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
    status: str            # "in_progress", "completed" или "failed"
    results: Optional[List[CheckResult]] = None
    error: Optional[str] = None

# Создаем FastAPI-приложение
app = FastAPI(
    title="Kaspersky Who Calls Checker API",
    version="1.3",
    dependencies=[Depends(get_api_key)]
)

async def cleanup_jobs():
    """Периодически удаляет старые задачи из памяти"""
    while True:
        now = datetime.utcnow()
        with jobs_lock:
            to_delete = []
            for job_id, info in jobs.items():
                created = info.get("created_at")
                if created and now - created > JOB_TTL:
                    to_delete.append(job_id)
            for jid in to_delete:
                del jobs[jid]
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

@app.on_event("startup")
async def start_cleanup_task():
    """Запускает фоновую корутину для очистки старых задач"""
    asyncio.create_task(cleanup_jobs())

async def _run_check(job_id: str, numbers: List[str], device: str):
    checker = KasperskyWhoCallsChecker(device)
    results: List[CheckResult] = []
    try:
        if not checker.launch_app():
            raise RuntimeError("Failed to launch Kaspersky Who Calls app on device")
        loop = asyncio.get_event_loop()
        for number in numbers:
            res: PhoneCheckResult = await loop.run_in_executor(None, checker.check_number, number)
            results.append(CheckResult(
                phone_number=res.phone_number,
                status=res.status,
                details=res.details
            ))
        await loop.run_in_executor(None, checker.close_app)
        with jobs_lock:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["results"] = results
    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)

@app.post("/check_numbers", response_model=JobResponse)
def submit_check(
    request: CheckRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key)
) -> JobResponse:
    """
    Создает задачу проверки телефонных номеров.
    Если предыдущая задача всё ещё выполняется, возвращает 429.
    Возвращает job_id для отслеживания.
    """
    with jobs_lock:
        if any(info.get("status") == "in_progress" for info in jobs.values()):
            raise HTTPException(status_code=429, detail="Previous task is still in progress")
        job_id = uuid.uuid4().hex
        jobs[job_id] = {
            "status": "in_progress",
            "results": None,
            "error": None,
            "created_at": datetime.utcnow()
        }
    adb_host = os.getenv("ADB_HOST", "127.0.0.1")
    adb_port = os.getenv("ADB_PORT", "5555")
    device = f"{adb_host}:{adb_port}"
    background_tasks.add_task(_run_check, job_id, request.numbers, device)
    return JobResponse(job_id=job_id)

@app.get("/status/{job_id}", response_model=StatusResponse)
def get_status(
    job_id: str,
    api_key: str = Depends(get_api_key)
) -> StatusResponse:
    """
    Возвращает статус и результаты задачи по job_id.
    """
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        results=job.get("results"),
        error=job.get("error")
    )
