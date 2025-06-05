from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from .auth import login, get_token
from .schemas import CheckRequest, CheckResult, JobResponse, StatusResponse
from . import jobs
from phone_spam_checker.exceptions import JobAlreadyRunningError

router = APIRouter()

router.post("/login")(login)


@router.post("/check_numbers", response_model=JobResponse)
def submit_check(
    request: CheckRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(get_token),
) -> JobResponse:
    try:
        job_id = jobs._new_job(request.service)
    except JobAlreadyRunningError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    if request.service not in {"auto", "kaspersky", "truecaller", "getcontact"}:
        raise HTTPException(status_code=400, detail="Unknown service")

    background_tasks.add_task(jobs.enqueue_job, job_id, request.numbers, request.service)
    return JobResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str, _: str = Depends(get_token)) -> StatusResponse:
    job = jobs.job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        results=job.get("results"),
        error=job.get("error"),
    )
