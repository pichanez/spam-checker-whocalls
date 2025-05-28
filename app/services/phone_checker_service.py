#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Refactored version of the phone checker service with improved typing and shorter functions.
"""

import logging
import asyncio
from typing import List, Dict, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
import uuid

from app.api.models import PhoneCheckResult
from app.repositories.cache_repository import PhoneCheckerCache
from app.infrastructure.device.device_interface import DeviceInterface
from app.infrastructure.checkers.phone_checker_strategy import PhoneCheckerStrategy, PhoneCheckerStrategyFactory
from app.utils.constants import PhoneStatus, CheckerSource, JobStatus
from app.utils.phone_utils import normalize_phone_number
from app.utils.protocols import CacheProtocol, PhoneCheckerProtocol

# Configure logging
logger = logging.getLogger("phone_checker.service")


class PhoneCheckerService:
    """Service for checking phone numbers against spam databases."""
    
    def __init__(self, cache: CacheProtocol, devices: Dict[str, DeviceInterface]):
        """
        Initialize the phone checker service.
        
        Args:
            cache: Cache repository
            devices: Dictionary of device name to device interface
        """
        self.cache = cache
        self.devices = devices
        self.strategies = PhoneCheckerStrategyFactory.create_all_strategies(devices)
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.active_jobs: Set[str] = set()
        self.job_ttl = timedelta(hours=1)
        self.max_concurrent_jobs = 3
    
    def create_job(self) -> str:
        """
        Create a new job.
        
        Returns:
            str: Job ID
        """
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = {
            "status": JobStatus.IN_PROGRESS,
            "results": None,
            "error": None,
            "created_at": datetime.utcnow(),
            "progress": 0.0,
        }
        self.active_jobs.add(job_id)
        return job_id
    
    def complete_job(self, job_id: str, results: List[PhoneCheckResult]) -> None:
        """
        Mark job as completed with results.
        
        Args:
            job_id: Job ID
            results: List of phone check results
        """
        if job_id in self.jobs:
            serialized_results = self._serialize_results(results)
            
            self.jobs[job_id]["status"] = JobStatus.COMPLETED
            self.jobs[job_id]["results"] = serialized_results
            self.jobs[job_id]["progress"] = 100.0
        
        if job_id in self.active_jobs:
            self.active_jobs.remove(job_id)
    
    def _serialize_results(self, results: List[PhoneCheckResult]) -> List[Dict[str, Any]]:
        """
        Serialize phone check results.
        
        Args:
            results: List of phone check results
            
        Returns:
            List[Dict[str, Any]]: Serialized results
        """
        return [
            {
                "phone_number": r.phone_number,
                "status": r.status,
                "details": r.details,
                "source": r.source
            }
            for r in results
        ]
    
    def fail_job(self, job_id: str, error: str) -> None:
        """
        Mark job as failed with error message.
        
        Args:
            job_id: Job ID
            error: Error message
        """
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = JobStatus.FAILED
            self.jobs[job_id]["error"] = error
        
        if job_id in self.active_jobs:
            self.active_jobs.remove(job_id)
    
    def update_progress(self, job_id: str, progress: float) -> None:
        """
        Update job progress.
        
        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
        """
        if job_id in self.jobs:
            self.jobs[job_id]["progress"] = min(99.0, progress)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status.
        
        Args:
            job_id: Job ID
            
        Returns:
            Optional[Dict[str, Any]]: Job status or None if job not found
        """
        return self.jobs.get(job_id)
    
    async def cleanup_jobs(self, interval_seconds: int = 60) -> None:
        """
        Remove old jobs periodically.
        
        Args:
            interval_seconds: Cleanup interval in seconds
        """
        while True:
            await self._perform_cleanup()
            await asyncio.sleep(interval_seconds)
    
    async def _perform_cleanup(self) -> None:
        """Perform job cleanup."""
        now = datetime.utcnow()
        outdated_jobs = self._find_outdated_jobs(now)
        
        for jid in outdated_jobs:
            self._remove_job(jid)
            
        logger.debug(f"Cleaned up {len(outdated_jobs)} outdated jobs")
    
    def _find_outdated_jobs(self, now: datetime) -> List[str]:
        """
        Find outdated jobs.
        
        Args:
            now: Current time
            
        Returns:
            List[str]: List of outdated job IDs
        """
        return [
            jid for jid, info in self.jobs.items()
            if now - info.get("created_at", now) > self.job_ttl
        ]
    
    def _remove_job(self, job_id: str) -> None:
        """
        Remove a job.
        
        Args:
            job_id: Job ID
        """
        if job_id in self.active_jobs:
            self.active_jobs.remove(job_id)
        if job_id in self.jobs:
            del self.jobs[job_id]
    
    async def check_number_with_cache(
        self, 
        phone: str, 
        strategy: PhoneCheckerProtocol,
        use_cache: bool = True
    ) -> PhoneCheckResult:
        """
        Check a phone number with caching.
        
        Args:
            phone: Phone number
            strategy: Phone checker strategy
            use_cache: Whether to use cache
            
        Returns:
            PhoneCheckResult: Check result
        """
        phone = normalize_phone_number(phone)
        
        # Try cache first if enabled
        if use_cache:
            cached_result = await self._get_from_cache(phone, strategy.source_name)
            if cached_result:
                return cached_result
        
        # Check with the actual strategy
        result = strategy.check_number(phone)

        # Cache the result
        if use_cache:
            await self._save_to_cache(result)
        
        return result
    
    async def _get_from_cache(self, phone: str, source: str) -> Optional[PhoneCheckResult]:
        """
        Get result from cache.
        
        Args:
            phone: Phone number
            source: Source name
            
        Returns:
            Optional[PhoneCheckResult]: Cached result or None if not found
        """
        cached_result = await self.cache.get(phone, source)
        if cached_result:
            logger.debug(f"Cache hit for {phone} from {source}")
            return cached_result
        
        logger.debug(f"Cache miss for {phone} from {source}")
        return None
    
    async def _save_to_cache(self, result: PhoneCheckResult) -> None:
        """
        Save result to cache.
        
        Args:
            result: Phone check result
        """
        await self.cache.set(result)
    
    async def check_numbers(
        self,
        job_id: str,
        numbers: List[str],
        use_cache: bool = True,
        force_source: Optional[str] = None
    ) -> None:
        """
        Check multiple phone numbers.
        
        Args:
            job_id: Job ID
            numbers: List of phone numbers
            use_cache: Whether to use cache
            force_source: Force using specific source
        """
        # Normalize and deduplicate numbers
        unique_numbers = self._normalize_and_deduplicate(numbers)
        total_numbers = len(unique_numbers)
        
        results: List[PhoneCheckResult] = []
        
        try:
            # Process numbers
            processed = 0
            for number in unique_numbers:
                result = await self._process_single_number(
                    number, force_source, use_cache
                )
                results.append(result)
                logger.info("%s", result)
                processed += 1
                self.update_progress(job_id, (processed / total_numbers) * 100)
                
                # Small delay to prevent overwhelming the device
                await asyncio.sleep(0.1)
            
        except Exception as e:
            self.fail_job(job_id, str(e))
            logger.error(f"Job {job_id} failed: {e}")
        else:
            self.complete_job(job_id, results)
            logger.info(f"Job {job_id} completed with {len(results)} results")
        finally:
            # Close all strategies
            self._close_all_strategies()
    
    def _normalize_and_deduplicate(self, numbers: List[str]) -> List[str]:
        """
        Normalize and deduplicate phone numbers.
        
        Args:
            numbers: List of phone numbers
            
        Returns:
            List[str]: List of normalized and deduplicated phone numbers
        """
        return list(dict.fromkeys([normalize_phone_number(n) for n in numbers]))
    
    async def _process_single_number(
        self, 
        number: str, 
        force_source: Optional[str],
        use_cache: bool
    ) -> PhoneCheckResult:
        """
        Process a single phone number.
        
        Args:
            number: Phone number
            force_source: Force using specific source
            use_cache: Whether to use cache
            
        Returns:
            PhoneCheckResult: Check result
        """
        # Determine which strategy to use
        strategy = self._get_strategy_for_number(number, force_source)
        
        # Skip if no suitable strategy found
        if not strategy:
            return PhoneCheckResult(
                phone_number=number,
                status=PhoneStatus.ERROR,
                details="No suitable checker available for this number",
                source=""
            )
        
        # Check the number
        try:
            return await self.check_number_with_cache(
                number, 
                strategy,
                use_cache
            )
        except Exception as e:
            logger.error(f"Error checking {number}: {e}")
            return PhoneCheckResult(
                phone_number=number,
                status=PhoneStatus.ERROR,
                details=str(e),
                source=strategy.source_name if hasattr(strategy, 'source_name') else ""
            )
    
    def _get_strategy_for_number(
        self, 
        number: str, 
        force_source: Optional[str]
    ) -> Optional[PhoneCheckerProtocol]:
        """
        Get strategy for a phone number.
        
        Args:
            number: Phone number
            force_source: Force using specific source
            
        Returns:
            Optional[PhoneCheckerProtocol]: Phone checker strategy or None if not found
        """
        if force_source:
            # Use forced source if specified
            return self.strategies.get(force_source)
        else:
            # Get appropriate strategy for the number
            return PhoneCheckerStrategyFactory.get_strategy_for_number(number, self.strategies)
    
    def _close_all_strategies(self) -> None:
        """Close all strategies."""
        for strategy in self.strategies.values():
            strategy.close_app()
    
    async def check_device_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all devices.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of device name to status
        """
        results = {}
        
        for name, device in self.devices.items():
            try:
                status = device.get_device_status()
                results[name] = status
            except Exception as e:
                results[name] = {
                    "connected": False,
                    "error": str(e)
                }
        
        return results
    
    async def clear_cache(self) -> Dict[str, Any]:
        """
        Clear the cache.
        
        Returns:
            Dict[str, Any]: Result of the operation
        """
        success = await self.cache.clear()
        return {
            "success": success,
            "message": "Cache cleared successfully" if success else "Failed to clear cache"
        }
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        return await self.cache.get_stats()
