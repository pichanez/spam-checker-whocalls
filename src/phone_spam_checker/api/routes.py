from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from .auth import login, get_token
from .schemas import CheckRequest, JobResponse, StatusResponse
from . import jobs
from phone_spam_checker.exceptions import JobAlreadyRunningError
from phone_spam_checker.job_manager import JobManager
from phone_spam_checker.dependencies import get_job_manager

router = APIRouter()

router.post("/login")(login)


@router.get("/health")
async def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}


@router.post("/check_numbers", response_model=JobResponse)
def submit_check(
    request: CheckRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    _: str = Depends(get_token),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    try:
        job_id = jobs._new_job(request.service, job_manager, request.numbers)
    except JobAlreadyRunningError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    if request.service not in {"auto", "kaspersky", "truecaller", "getcontact", "tbank"}:
        raise HTTPException(status_code=400, detail="Unknown service")

    background_tasks.add_task(
        jobs.enqueue_job, job_id, request.numbers, request.service, http_request.app
    )
    return JobResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=StatusResponse)
def get_status(
    job_id: str, job_manager: JobManager = Depends(get_job_manager), _: str = Depends(get_token)
) -> StatusResponse:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        results=job.get("results"),
        error=job.get("error"),
    )
