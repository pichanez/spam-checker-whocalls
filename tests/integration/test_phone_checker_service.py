#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for the phone checker service.
"""

import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from app.services.phone_checker_service import PhoneCheckerService
from app.repositories.cache_repository import PhoneCheckerCache
from app.infrastructure.device.android_device import AndroidDevice
from app.api.models import PhoneCheckResult
from app.utils.constants import PhoneStatus, CheckerSource


@pytest.fixture
async def mock_cache():
    """Create a mock cache."""
    cache = MagicMock(spec=PhoneCheckerCache)
    
    # Mock connect method
    cache.connect.return_value = True
    
    # Mock get method
    cache.get.return_value = None
    
    # Mock set method
    cache.set.return_value = True
    
    return cache


@pytest.fixture
def mock_device():
    """Create a mock device."""
    device = MagicMock(spec=AndroidDevice)
    
    # Mock connect method
    device.connect.return_value = True
    
    # Mock launch_app method
    device.launch_app.return_value = True
    
    # Mock click_element method
    device.click_element.return_value = True
    
    # Mock input_text method
    device.input_text.return_value = True
    
    # Mock element_exists method
    device.element_exists.return_value = False
    
    # Mock get_element_text method
    device.get_element_text.return_value = "Test Name"
    
    # Mock get_device_status method
    device.get_device_status.return_value = {
        "connected": True,
        "screen_on": True,
        "unlocked": True,
        "battery": "80%",
        "running_apps": "",
        "error": None
    }
    
    return device


@pytest.fixture
def phone_checker_service(mock_cache, mock_device):
    """Create a phone checker service with mock dependencies."""
    devices = {
        CheckerSource.KASPERSKY: mock_device,
        CheckerSource.TRUECALLER: mock_device,
        CheckerSource.GETCONTACT: mock_device
    }
    
    return PhoneCheckerService(mock_cache, devices)


@pytest.mark.asyncio
async def test_check_numbers_job(phone_checker_service):
    """Test checking numbers job."""
    # Create a job
    job_id = phone_checker_service.create_job()
    
    # Check numbers
    await phone_checker_service.check_numbers(
        job_id=job_id,
        numbers=["+79123456789", "+12025550108"],
        use_cache=True
    )
    
    # Get job status
    job_status = phone_checker_service.get_job_status(job_id)
    
    # Assert job is completed
    assert job_status["status"] == "completed"
    assert job_status["progress"] == 100.0
    assert job_status["results"] is not None
    assert len(job_status["results"]) == 2


@pytest.mark.asyncio
async def test_check_numbers_with_cache(phone_checker_service, mock_cache):
    """Test checking numbers with cache hit."""
    # Mock cache hit
    mock_cache.get.return_value = PhoneCheckResult(
        phone_number="+79123456789",
        status=PhoneStatus.SAFE,
        details="Cached result",
        source=CheckerSource.KASPERSKY
    )
    
    # Create a job
    job_id = phone_checker_service.create_job()
    
    # Check numbers
    await phone_checker_service.check_numbers(
        job_id=job_id,
        numbers=["+79123456789"],
        use_cache=True
    )
    
    # Get job status
    job_status = phone_checker_service.get_job_status(job_id)
    
    # Assert job is completed with cached result
    assert job_status["status"] == "completed"
    assert job_status["results"][0]["status"] == PhoneStatus.SAFE
    assert job_status["results"][0]["details"] == "Cached result"
    assert job_status["results"][0]["source"] == CheckerSource.KASPERSKY


@pytest.mark.asyncio
async def test_check_device_health(phone_checker_service):
    """Test checking device health."""
    # Check device health
    health = await phone_checker_service.check_device_health()
    
    # Assert all devices are healthy
    assert CheckerSource.KASPERSKY in health
    assert health[CheckerSource.KASPERSKY]["connected"] is True
    assert health[CheckerSource.KASPERSKY]["screen_on"] is True
    
    assert CheckerSource.TRUECALLER in health
    assert health[CheckerSource.TRUECALLER]["connected"] is True
    
    assert CheckerSource.GETCONTACT in health
    assert health[CheckerSource.GETCONTACT]["connected"] is True


@pytest.mark.asyncio
async def test_cache_operations(phone_checker_service, mock_cache):
    """Test cache operations."""
    # Test clear cache
    mock_cache.clear.return_value = True
    result = await phone_checker_service.clear_cache()
    assert result["success"] is True
    
    # Test get cache stats
    mock_cache.get_stats.return_value = {
        "enabled": True,
        "connected": True,
        "entries": 10,
        "ttl": 86400
    }
    stats = await phone_checker_service.get_cache_stats()
    assert stats["enabled"] is True
    assert stats["entries"] == 10


@pytest.mark.asyncio
async def test_job_cleanup(phone_checker_service):
    """Test job cleanup."""
    # Create some jobs
    job_id1 = phone_checker_service.create_job()
    job_id2 = phone_checker_service.create_job()
    
    # Complete one job
    phone_checker_service.complete_job(job_id1, [])
    
    # Fail one job
    phone_checker_service.fail_job(job_id2, "Test error")
    
    # Perform cleanup
    await phone_checker_service._perform_cleanup()
    
    # Jobs should still exist (not old enough)
    assert job_id1 in phone_checker_service.jobs
    assert job_id2 in phone_checker_service.jobs
    
    # Manually set created_at to old date to trigger cleanup
    import datetime
    old_date = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    phone_checker_service.jobs[job_id1]["created_at"] = old_date
    phone_checker_service.jobs[job_id2]["created_at"] = old_date
    
    # Perform cleanup again
    await phone_checker_service._perform_cleanup()
    
    # Jobs should be removed
    assert job_id1 not in phone_checker_service.jobs
    assert job_id2 not in phone_checker_service.jobs
