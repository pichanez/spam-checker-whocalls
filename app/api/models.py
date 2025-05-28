#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Models for the phone-spam-checker application.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator

from app.utils.constants import PhoneStatus, JobStatus, CheckerSource
from app.utils.phone_utils import normalize_phone_number


@dataclass
class PhoneCheckResult:
    """Result of a phone number check."""
    phone_number: str
    status: str  # Use PhoneStatus constants
    details: str = ""
    source: str = ""  # Use CheckerSource constants


class CheckRequest(BaseModel):
    """Request model for checking phone numbers."""
    numbers: List[str] = Field(..., description="List of phone numbers to check")
    use_cache: bool = Field(True, description="Whether to use cached results if available")
    force_source: Optional[str] = Field(None, description="Force using specific source: 'kaspersky', 'truecaller', or 'getcontact'")
    
    @validator('numbers')
    def normalize_numbers(cls, v):
        """Normalize phone numbers."""
        return [normalize_phone_number(phone) for phone in v]
    
    @validator('force_source')
    def validate_source(cls, v):
        """Validate source."""
        if v and v not in CheckerSource.all_sources():
            raise ValueError(f"Invalid source: {v}. Must be one of: {', '.join(CheckerSource.all_sources())}")
        return v


class JobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str = Field(..., description="Unique job identifier")


class CheckResult(BaseModel):
    """Model for check result."""
    phone_number: str = Field(..., description="Phone number that was checked")
    status: str = Field(..., description="Status: 'Safe', 'Spam', 'Not in database', 'Error', 'Unknown'")
    details: str = Field("", description="Additional details about the result")
    source: str = Field("", description="Source of the information (which checker provided it)")


class StatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status: 'in_progress', 'completed', 'failed'")
    results: Optional[List[CheckResult]] = Field(None, description="Check results if job is completed")
    error: Optional[str] = Field(None, description="Error message if job failed")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")


class DeviceStatus(BaseModel):
    """Model for device status."""
    connected: bool = Field(..., description="Whether the device is connected")
    screen_on: Optional[bool] = Field(None, description="Whether the screen is on")
    unlocked: Optional[bool] = Field(None, description="Whether the device is unlocked")
    battery: Optional[str] = Field(None, description="Battery level")
    running_apps: Optional[str] = Field(None, description="Running relevant apps")
    error: Optional[str] = Field(None, description="Error message if any")


class DeviceStatusResponse(BaseModel):
    """Response model for device status."""
    kaspersky: DeviceStatus = Field(..., description="Kaspersky device status")
    truecaller: DeviceStatus = Field(..., description="Truecaller device status")
    getcontact: DeviceStatus = Field(..., description="GetContact device status")


class CacheResponse(BaseModel):
    """Response model for cache operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message about the operation")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Service status")
