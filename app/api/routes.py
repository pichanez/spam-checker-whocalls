#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API routes for the phone-spam-checker application.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Security, Request
from fastapi.security.api_key import APIKeyHeader
from prometheus_client import Counter, Histogram

from app.api.models import (
    CheckRequest, JobResponse, StatusResponse, DeviceStatusResponse,
    CacheResponse, HealthResponse
)
from app.services.phone_checker_service import PhoneCheckerService
from app.utils.constants import JobStatus

# Configure logging
logger = logging.getLogger("phone_checker.api.routes")

# API key authorization
API_KEY = os.getenv("API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Prometheus metrics
REQUESTS_TOTAL = Counter('phone_checker_requests_total', 'Total number of requests', ['endpoint'])
CHECK_DURATION = Histogram('phone_checker_check_duration_seconds', 'Time spent checking phone numbers')
CACHE_HITS = Counter('phone_checker_cache_hits_total', 'Total number of cache hits')
CACHE_MISSES = Counter('phone_checker_cache_misses_total', 'Total number of cache misses')

# Create router
router = APIRouter()


# Authentication dependency
async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Validate API key.
    
    Args:
        api_key: API key from request header
        
    Returns:
        str: Validated API key
        
    Raises:
        HTTPException: If API key is invalid
    """
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key


# Service dependency
async def get_phone_checker_service() -> PhoneCheckerService:
    """
    Get phone checker service instance.
    
    Returns:
        PhoneCheckerService: Phone checker service
    """
    from app.main import phone_checker_service
    return phone_checker_service


@router.post("/check_numbers", response_model=JobResponse)
async def check_numbers(
    request: CheckRequest,
    background_tasks: BackgroundTasks,
    service: PhoneCheckerService = Depends(get_phone_checker_service),
    api_key: str = Depends(get_api_key)
):
    """
    Check phone numbers for spam.
    
    Args:
        request: Check request
        background_tasks: Background tasks
        service: Phone checker service
        api_key: API key
        
    Returns:
        JobResponse: Job response with job ID
    """
    REQUESTS_TOTAL.labels(endpoint="/check_numbers").inc()
    
    # Create job
    job_id = service.create_job()
    
    # Start background task
    background_tasks.add_task(
        service.check_numbers,
        job_id=job_id,
        numbers=request.numbers,
        use_cache=request.use_cache,
        force_source=request.force_source
    )
    
    return JobResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(
    job_id: str,
    service: PhoneCheckerService = Depends(get_phone_checker_service),
    api_key: str = Depends(get_api_key)
):
    """
    Get job status.
    
    Args:
        job_id: Job ID
        service: Phone checker service
        api_key: API key
        
    Returns:
        StatusResponse: Job status
        
    Raises:
        HTTPException: If job not found
    """
    REQUESTS_TOTAL.labels(endpoint="/status").inc()
    
    job_info = service.get_job_status(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return StatusResponse(
        job_id=job_id,
        status=job_info["status"],
        results=job_info.get("results"),
        error=job_info.get("error"),
        progress=job_info.get("progress")
    )


@router.get("/device_status", response_model=DeviceStatusResponse)
async def device_status(
    service: PhoneCheckerService = Depends(get_phone_checker_service),
    api_key: str = Depends(get_api_key)
):
    """
    Get device status.
    
    Args:
        service: Phone checker service
        api_key: API key
        
    Returns:
        DeviceStatusResponse: Device status
    """
    REQUESTS_TOTAL.labels(endpoint="/device_status").inc()
    
    status = await service.check_device_health()
    
    return DeviceStatusResponse(
        kaspersky=status.get("kaspersky", {"connected": False, "error": "Device not configured"}),
        truecaller=status.get("truecaller", {"connected": False, "error": "Device not configured"}),
        getcontact=status.get("getcontact", {"connected": False, "error": "Device not configured"})
    )


@router.post("/cache/clear", response_model=CacheResponse)
async def clear_cache(
    service: PhoneCheckerService = Depends(get_phone_checker_service),
    api_key: str = Depends(get_api_key)
):
    """
    Clear cache.
    
    Args:
        service: Phone checker service
        api_key: API key
        
    Returns:
        CacheResponse: Cache operation result
    """
    REQUESTS_TOTAL.labels(endpoint="/cache/clear").inc()
    
    result = await service.clear_cache()
    
    return CacheResponse(
        success=result["success"],
        message=result["message"]
    )


@router.get("/cache/stats", response_model=Dict[str, Any])
async def cache_stats(
    service: PhoneCheckerService = Depends(get_phone_checker_service),
    api_key: str = Depends(get_api_key)
):
    """
    Get cache statistics.
    
    Args:
        service: Phone checker service
        api_key: API key
        
    Returns:
        Dict[str, Any]: Cache statistics
    """
    REQUESTS_TOTAL.labels(endpoint="/cache/stats").inc()
    
    return await service.get_cache_stats()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: Health status
    """
    REQUESTS_TOTAL.labels(endpoint="/health").inc()
    
    return HealthResponse(status="ok")
