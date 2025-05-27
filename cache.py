#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache module for phone checker API.
Provides Redis-based caching functionality for phone check results.
"""

import json
import logging
import os
from datetime import timedelta
from typing import Optional, Dict, Any, List, Union

import redis
from pydantic import BaseModel

from base_phone_checker import PhoneCheckResult

# Configure logger
logger = logging.getLogger("phone_checker.cache")

# Default cache settings
DEFAULT_CACHE_TTL = 86400  # 24 hours in seconds
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class CacheConfig(BaseModel):
    """Configuration for cache module."""
    redis_url: str = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    ttl: int = int(os.getenv("CACHE_TTL", DEFAULT_CACHE_TTL))
    enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"


class PhoneCheckerCache:
    """Redis-based cache for phone check results."""

    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize the cache with configuration.
        
        Args:
            config: Cache configuration, uses environment variables if not provided
        """
        self.config = config or CacheConfig()
        self._redis = None
        
        if self.config.enabled:
            try:
                self._redis = redis.from_url(self.config.redis_url)
                logger.info(f"Cache initialized with Redis at {self.config.redis_url}")
            except Exception as e:
                logger.error(f"Failed to initialize Redis cache: {e}")
                self._redis = None
        else:
            logger.info("Cache is disabled by configuration")

    @property
    def is_available(self) -> bool:
        """Check if cache is available and enabled."""
        if not self.config.enabled or not self._redis:
            return False
            
        try:
            self._redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection error: {e}")
            return False

    def _get_key(self, phone: str, source: Optional[str] = None) -> str:
        """
        Generate cache key for a phone number.
        
        Args:
            phone: Phone number
            source: Optional source name (checker)
            
        Returns:
            str: Cache key
        """
        if source:
            return f"phone_check:{phone}:{source}"
        return f"phone_check:{phone}"

    async def get(self, phone: str, source: Optional[str] = None) -> Optional[PhoneCheckResult]:
        """
        Get cached result for a phone number.
        
        Args:
            phone: Phone number
            source: Optional source name (checker)
            
        Returns:
            Optional[PhoneCheckResult]: Cached result or None if not found
        """
        if not self.is_available:
            return None
            
        try:
            key = self._get_key(phone, source)
            data = self._redis.get(key)
            if data:
                json_data = json.loads(data)
                return PhoneCheckResult(**json_data)
        except Exception as e:
            logger.error(f"Error getting cache for {phone}: {e}")
        
        return None

    async def set(self, result: PhoneCheckResult, ttl: Optional[int] = None) -> bool:
        """
        Cache a phone check result.
        
        Args:
            result: Phone check result
            ttl: Time to live in seconds, uses default if not provided
            
        Returns:
            bool: True if cached successfully, False otherwise
        """
        if not self.is_available:
            return False
            
        try:
            key = self._get_key(result.phone_number, result.source)
            data = json.dumps({
                "phone_number": result.phone_number,
                "status": result.status,
                "details": result.details,
                "source": result.source
            })
            self._redis.setex(key, ttl or self.config.ttl, data)
            
            # Also set a generic key without source
            if result.source:
                generic_key = self._get_key(result.phone_number)
                self._redis.setex(generic_key, ttl or self.config.ttl, data)
                
            return True
        except Exception as e:
            logger.error(f"Error setting cache for {result.phone_number}: {e}")
            return False

    async def delete(self, phone: str, source: Optional[str] = None) -> bool:
        """
        Delete cached result for a phone number.
        
        Args:
            phone: Phone number
            source: Optional source name (checker)
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self.is_available:
            return False
            
        try:
            key = self._get_key(phone, source)
            self._redis.delete(key)
            
            # Also delete generic key if no source specified
            if not source:
                pattern = f"phone_check:{phone}:*"
                for key in self._redis.scan_iter(pattern):
                    self._redis.delete(key)
                    
            return True
        except Exception as e:
            logger.error(f"Error deleting cache for {phone}: {e}")
            return False

    async def get_multiple(self, phones: List[str], source: Optional[str] = None) -> Dict[str, PhoneCheckResult]:
        """
        Get cached results for multiple phone numbers.
        
        Args:
            phones: List of phone numbers
            source: Optional source name (checker)
            
        Returns:
            Dict[str, PhoneCheckResult]: Dictionary of phone number to result
        """
        results = {}
        if not self.is_available:
            return results
            
        try:
            pipeline = self._redis.pipeline()
            keys = [self._get_key(phone, source) for phone in phones]
            
            for key in keys:
                pipeline.get(key)
                
            data_list = pipeline.execute()
            
            for phone, data in zip(phones, data_list):
                if data:
                    json_data = json.loads(data)
                    results[phone] = PhoneCheckResult(**json_data)
        except Exception as e:
            logger.error(f"Error getting multiple cache entries: {e}")
            
        return results

    async def set_multiple(self, results: List[PhoneCheckResult], ttl: Optional[int] = None) -> bool:
        """
        Cache multiple phone check results.
        
        Args:
            results: List of phone check results
            ttl: Time to live in seconds, uses default if not provided
            
        Returns:
            bool: True if all cached successfully, False otherwise
        """
        if not self.is_available or not results:
            return False
            
        try:
            pipeline = self._redis.pipeline()
            expiry = ttl or self.config.ttl
            
            for result in results:
                key = self._get_key(result.phone_number, result.source)
                data = json.dumps({
                    "phone_number": result.phone_number,
                    "status": result.status,
                    "details": result.details,
                    "source": result.source
                })
                pipeline.setex(key, expiry, data)
                
                # Also set a generic key without source
                if result.source:
                    generic_key = self._get_key(result.phone_number)
                    pipeline.setex(generic_key, expiry, data)
            
            pipeline.execute()
            return True
        except Exception as e:
            logger.error(f"Error setting multiple cache entries: {e}")
            return False

    async def clear_all(self) -> bool:
        """
        Clear all cached results.
        
        Returns:
            bool: True if cleared successfully, False otherwise
        """
        if not self.is_available:
            return False
            
        try:
            pattern = "phone_check:*"
            keys = list(self._redis.scan_iter(pattern))
            if keys:
                self._redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False


# Singleton instance
_cache_instance = None


def get_cache() -> PhoneCheckerCache:
    """
    Get or create the cache singleton instance.
    
    Returns:
        PhoneCheckerCache: Cache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = PhoneCheckerCache()
    return _cache_instance
