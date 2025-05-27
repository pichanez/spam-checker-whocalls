#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phone Checker API — Kaspersky / Truecaller / GetContact
Fixed version with proper async processing to prevent /status endpoint hanging.
"""

import os
import uuid
import asyncio
import re
import socket
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Set
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, start_http_server

# Import base classes and utilities
from base_phone_checker import (
    BasePhoneChecker,
    PhoneCheckResult,
    PhoneCheckerError,
    DeviceConnectionError,
    normalize_phone_number
)

# Import checkers
from kaspersky_phone_checker import KasperskyWhoCallsChecker
from truecaller_phone_checker import TruecallerChecker
from getcontact_phone_checker import GetContactChecker

# Import cache
from cache import get_cache, PhoneCheckerCache

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("phone_checker.api")

# API key authorization
API_KEY = os.getenv("API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Prometheus metrics
REQUESTS_TOTAL = Counter('phone_checker_requests_total', 'Total number of requests', ['endpoint'])
CHECK_DURATION = Histogram('phone_checker_check_duration_seconds', 'Time spent checking phone numbers')
CACHE_HITS = Counter('phone_checker_cache_hits_total', 'Total number of cache hits')
CACHE_MISSES = Counter('phone_checker_cache_misses_total', 'Total number of cache misses')

# Background job parameters
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))
JOB_TTL = timedelta(hours=int(os.getenv("JOB_TTL_HOURS", "1")))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

# Job storage
jobs: Dict[str, Dict[str, Any]] = {}
active_jobs: Set[str] = set()

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)

# Device configuration
DEVICE_CONFIG = {
    "kaspersky_device": f"{os.getenv('KASP_ADB_HOST', '127.0.0.1')}:{os.getenv('KASP_ADB_PORT', '5555')}",
    "truecaller_device": f"{os.getenv('TC_ADB_HOST', '127.0.0.1')}:{os.getenv('TC_ADB_PORT', '5556')}",
    "getcontact_device": f"{os.getenv('GC_ADB_HOST', '127.0.0.1')}:{os.getenv('GC_ADB_PORT', '5557')}"
}

# Pydantic models
class CheckRequest(BaseModel):
    numbers: List[str] = Field(..., description="List of phone numbers to check")
    use_cache: bool = Field(True, description="Whether to use cached results if available")
    force_source: Optional[str] = Field(None, description="Force using specific source: 'kaspersky', 'truecaller', or 'getcontact'")


class JobResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")


class CheckResult(BaseModel):
    phone_number: str = Field(..., description="Phone number that was checked")
    status: str = Field(..., description="Status: 'Safe', 'Spam', 'Not in database', 'Error', 'Unknown'")
    details: str = Field("", description="Additional details about the result")
    source: str = Field("", description="Source of the information (which checker provided it)")


class StatusResponse(BaseModel):
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status: 'in_progress', 'completed', 'failed'")
    results: Optional[List[CheckResult]] = Field(None, description="Check results if job is completed")
    error: Optional[str] = Field(None, description="Error message if job failed")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")


class DeviceStatus(BaseModel):
    connected: bool = Field(..., description="Whether the device is connected")
    screen_on: Optional[bool] = Field(None, description="Whether the screen is on")
    unlocked: Optional[bool] = Field(None, description="Whether the device is unlocked")
    battery: Optional[str] = Field(None, description="Battery level")
    running_apps: Optional[str] = Field(None, description="Running relevant apps")
    error: Optional[str] = Field(None, description="Error message if any")


class DeviceStatusResponse(BaseModel):
    kaspersky: DeviceStatus = Field(..., description="Kaspersky device status")
    truecaller: DeviceStatus = Field(..., description="Truecaller device status")
    getcontact: DeviceStatus = Field(..., description="GetContact device status")


# FastAPI app
app = FastAPI(
    title="Phone Checker API",
    version="3.0",
    description="API for checking phone numbers against spam databases using Kaspersky Who Calls, Truecaller, and GetContact",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication dependency
async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate API key."""
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key


# Cache dependency
async def get_cache_instance() -> PhoneCheckerCache:
    """Get cache instance."""
    return get_cache()


# Background tasks
async def cleanup_jobs() -> None:
    """Remove old jobs periodically."""
    while True:
        now = datetime.utcnow()
        outdated_jobs = []
        
        for jid, info in jobs.items():
            if now - info.get("created_at", now) > JOB_TTL:
                outdated_jobs.append(jid)
                
        for jid in outdated_jobs:
            if jid in active_jobs:
                active_jobs.remove(jid)
            if jid in jobs:
                del jobs[jid]
                
        logger.debug(f"Cleaned up {len(outdated_jobs)} outdated jobs")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_background_tasks() -> None:
    """Start background tasks on app startup."""
    # Start metrics server
    try:
        metrics_port = int(os.getenv("METRICS_PORT", "8001"))
        start_http_server(metrics_port)
        logger.info(f"Started Prometheus metrics server on port {metrics_port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
    
    # Start cleanup task
    asyncio.create_task(cleanup_jobs())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    executor.shutdown(wait=True)


# Helper functions
async def _ping_device_async(host: str, port: str, timeout: int = 5) -> None:
    """Check if device is reachable (async version)."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            executor,
            lambda: socket.create_connection((host, int(port)), timeout=timeout).close()
        )
    except Exception as e:
        raise DeviceConnectionError(f"Cannot reach device {host}:{port}: {e}") from e


def _new_job() -> str:
    """Create a new job entry."""
    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "status": "in_progress",
        "results": None,
        "error": None,
        "created_at": datetime.utcnow(),
        "progress": 0.0,
    }
    active_jobs.add(job_id)
    return job_id


def _complete_job(job_id: str, results: List[PhoneCheckResult]) -> None:
    """Mark job as completed with results."""
    if job_id in jobs:
        serialized_results = [
            {
                "phone_number": r.phone_number,
                "status": r.status,
                "details": r.details,
                "source": r.source
            }
            for r in results
        ]
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["results"] = serialized_results
        jobs[job_id]["progress"] = 100.0
    
    if job_id in active_jobs:
        active_jobs.remove(job_id)


def _fail_job(job_id: str, error: str) -> None:
    """Mark job as failed with error message."""
    if job_id in jobs:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = error
    
    if job_id in active_jobs:
        active_jobs.remove(job_id)


def _update_progress(job_id: str, progress: float) -> None:
    """Update job progress."""
    if job_id in jobs:
        jobs[job_id]["progress"] = min(99.0, progress)


async def check_device_health(device_id: str) -> DeviceStatus:
    """Check health of an Android device (async)."""
    loop = asyncio.get_event_loop()
    
    def _check_sync():
        try:
            import uiautomator2 as u2
            
            d = u2.connect(device_id)
            info = d.info
            
            # Get battery info
            battery_output = d.shell("dumpsys battery | grep level").output.strip()
            battery_level = battery_output.split(":")[-1].strip() if battery_output else "Unknown"
            
            # Check running apps
            apps_output = d.shell("ps | grep -e com.truecaller -e com.kaspersky -e app.source.getcontact").output.strip()
            
            return DeviceStatus(
                connected=True,
                screen_on=info.get("screenOn", False),
                unlocked=not info.get("screenLocked", True),
                battery=f"{battery_level}%",
                running_apps=apps_output or "None",
                error=None
            )
        except Exception as e:
            return DeviceStatus(
                connected=False,
                error=str(e)
            )
    
    return await loop.run_in_executor(executor, _check_sync)


# Checker implementation
async def _check_number_with_cache(
    phone: str, 
    checker: BasePhoneChecker, 
    cache: PhoneCheckerCache,
    use_cache: bool = True
) -> PhoneCheckResult:
    """Check a phone number with caching (async)."""
    phone = normalize_phone_number(phone)
    
    # Try cache first if enabled
    if use_cache:
        cached_result = await cache.get(phone, checker.source_name)
        if cached_result:
            CACHE_HITS.inc()
            logger.debug(f"Cache hit for {phone} from {checker.source_name}")
            return cached_result
        
        CACHE_MISSES.inc()
        logger.debug(f"Cache miss for {phone} from {checker.source_name}")
    
    # Check with the actual checker in thread pool
    loop = asyncio.get_event_loop()
    with CHECK_DURATION.time():
        result = await loop.run_in_executor(executor, checker.check_number, phone)
    
    # Cache the result
    if use_cache:
        await cache.set(result)
    
    return result


async def _initialize_checker(checker_type: str, device_id: str) -> BasePhoneChecker:
    """Initialize a checker asynchronously."""
    loop = asyncio.get_event_loop()
    
    # Ping device
    host, port = device_id.split(":")
    await _ping_device_async(host, port)
    
    # Create checker instance
    def _create_and_launch():
        if checker_type == "kaspersky":
            checker = KasperskyWhoCallsChecker(device_id)
        elif checker_type == "truecaller":
            checker = TruecallerChecker(device_id)
        elif checker_type == "getcontact":
            checker = GetContactChecker(device_id)
        else:
            raise ValueError(f"Unknown checker type: {checker_type}")
        
        if not checker.launch_app():
            raise RuntimeError(f"Failed to launch {checker_type}")
        
        return checker
    
    return await loop.run_in_executor(executor, _create_and_launch)


async def _run_check_async(
    job_id: str, 
    numbers: List[str], 
    use_cache: bool = True,
    force_source: Optional[str] = None,
    cache: Optional[PhoneCheckerCache] = None
) -> None:
    """Run phone number checks asynchronously."""
    if not cache:
        cache = get_cache()
    
    # Normalize and deduplicate numbers
    unique_numbers = list(dict.fromkeys([normalize_phone_number(n) for n in numbers]))
    total_numbers = len(unique_numbers)
    
    checkers = {}
    results: List[PhoneCheckResult] = []
    
    try:
        # Initialize checkers based on force_source parameter
        if force_source:
            # Single source mode
            device_id = DEVICE_CONFIG[f"{force_source}_device"]
            checkers[force_source] = await _initialize_checker(force_source, device_id)
        else:
            # Determine which checkers we need
            kasp_nums = [n for n in unique_numbers if re.match(r"^(\+7|7)9", n)]
            tc_nums = [n for n in unique_numbers if n not in kasp_nums]
            
            # Initialize checkers in parallel
            init_tasks = []
            
            if kasp_nums:
                init_tasks.append(
                    _initialize_checker("kaspersky", DEVICE_CONFIG["kaspersky_device"])
                )
            
            if tc_nums:
                init_tasks.append(
                    _initialize_checker("truecaller", DEVICE_CONFIG["truecaller_device"])
                )
            
            # Wait for all checkers to initialize
            if init_tasks:
                initialized = await asyncio.gather(*init_tasks, return_exceptions=True)
                
                # Handle results
                if kasp_nums and not isinstance(initialized[0], Exception):
                    checkers["kaspersky"] = initialized[0]
                
                if tc_nums:
                    idx = 1 if kasp_nums else 0
                    if idx < len(initialized) and not isinstance(initialized[idx], Exception):
                        checkers["truecaller"] = initialized[idx]
        
        # Process numbers
        processed = 0
        for number in unique_numbers:
            # Determine which checker to use
            checker_key = force_source
            if not checker_key:
                checker_key = "kaspersky" if re.match(r"^(\+7|7)9", number) else "truecaller"
            
            # Skip if we don't have this checker
            if checker_key not in checkers:
                results.append(PhoneCheckResult(
                    phone_number=number,
                    status="Error",
                    details=f"No suitable checker available for this number",
                    source=""
                ))
                processed += 1
                _update_progress(job_id, (processed / total_numbers) * 100)
                continue
            
            # Check the number
            try:
                result = await _check_number_with_cache(
                    number, 
                    checkers[checker_key], 
                    cache,
                    use_cache
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error checking {number}: {e}")
                results.append(PhoneCheckResult(
                    phone_number=number,
                    status="Error",
                    details=str(e),
                    source=checker_key
                ))
            
            processed += 1
            _update_progress(job_id, (processed / total_numbers) * 100)
            
            # Small delay to prevent overwhelming the device
            await asyncio.sleep(0.1)
        
    except Exception as e:
        _fail_job(job_id, str(e))
        logger.error(f"Job {job_id} failed: {e}")
    else:
        _complete_job(job_id, results)
        logger.info(f"Job {job_id} completed with {len(results)} results")
    finally:
        # Close all checkers
        close_tasks = []
        for name, checker in checkers.items():
            async def close_checker(c, n):
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(executor, c.close_app)
                except Exception as e:
                    logger.error(f"Error closing {n} app: {e}")
            
            close_tasks.append(close_checker(checker, name))
        
        if close_tasks:
            await asyncio.gather(*close_tasks)


# API endpoints
@app.post(
    "/check_numbers", 
    response_model=JobResponse,
    summary="Check phone numbers",
    description="Submit phone numbers for checking against spam databases"
)
async def submit_check(
    request: CheckRequest, 
    background_tasks: BackgroundTasks,
    cache: PhoneCheckerCache = Depends(get_cache_instance),
    _: str = Depends(get_api_key)
) -> JobResponse:
    """Submit phone numbers for checking."""
    REQUESTS_TOTAL.labels(endpoint="check_numbers").inc()
    
    # Check if we have too many active jobs
    if len(active_jobs) >= MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429, 
            detail=f"Too many concurrent jobs (max {MAX_CONCURRENT_JOBS})"
        )
    
    # Create new job
    job_id = _new_job()
    
    # Create a task instead of using background_tasks
    asyncio.create_task(
        _run_check_async(
            job_id,
            request.numbers,
            request.use_cache,
            request.force_source,
            cache
        )
    )
    
    return JobResponse(job_id=job_id)


@app.get(
    "/status/{job_id}", 
    response_model=StatusResponse,
    summary="Get job status",
    description="Get status and results of a previously submitted job"
)
async def get_status(
    job_id: str, 
    _: str = Depends(get_api_key)
) -> StatusResponse:
    """Get status of a job."""
    REQUESTS_TOTAL.labels(endpoint="status").inc()
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    # Get job data - this is fast as it's just dictionary access
    job_data = jobs[job_id]
    
    # Return status immediately
    return StatusResponse(
        job_id=job_id,
        status=job_data["status"],
        results=job_data.get("results"),
        error=job_data.get("error"),
        progress=job_data.get("progress", 0.0)
    )


@app.get(
    "/device_status", 
    response_model=DeviceStatusResponse,
    summary="Get device status",
    description="Get status of all connected Android devices"
)
async def get_device_status(
    _: str = Depends(get_api_key)
) -> DeviceStatusResponse:
    """Get status of all devices."""
    REQUESTS_TOTAL.labels(endpoint="device_status").inc()
    
    # Check all devices in parallel
    kaspersky_task = check_device_health(DEVICE_CONFIG["kaspersky_device"])
    truecaller_task = check_device_health(DEVICE_CONFIG["truecaller_device"])
    getcontact_task = check_device_health(DEVICE_CONFIG["getcontact_device"])
    
    kaspersky_status, truecaller_status, getcontact_status = await asyncio.gather(
        kaspersky_task, truecaller_task, getcontact_task
    )
    
    return DeviceStatusResponse(
        kaspersky=kaspersky_status,
        truecaller=truecaller_status,
        getcontact=getcontact_status
    )


@app.post(
    "/cache/clear", 
    summary="Clear cache",
    description="Clear all cached results"
)
async def clear_cache(
    cache: PhoneCheckerCache = Depends(get_cache_instance),
    _: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """Clear all cached results."""
    REQUESTS_TOTAL.labels(endpoint="cache_clear").inc()
    
    success = await cache.clear_all()
    return {
        "success": success,
        "message": "Cache cleared successfully" if success else "Failed to clear cache"
    }


@app.get(
    "/health", 
    summary="Health check",
    description="Check if the API is running"
)
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint."""
    REQUESTS_TOTAL.labels(endpoint="health").inc()
    return {"status": "ok"}


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Phone Checker API",
        version="3.0",
        description="API for checking phone numbers against spam databases",
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": API_KEY_NAME
        }
    }
    
    # Apply security globally
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi