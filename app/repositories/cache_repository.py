#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache repository for phone check results.
"""

import json
import logging
from typing import Optional, Dict, Any

import redis
from redis.asyncio import Redis

from app.api.models import PhoneCheckResult
from app.utils.constants import CacheKeys
from app.utils.exceptions import CacheError

# Configure logging
logger = logging.getLogger("phone_checker.cache")


class PhoneCheckerCache:
    """Cache for phone checker results."""
    
    def __init__(self, redis_url: str, ttl: int = 86400, enabled: bool = True):
        """
        Initialize the cache.
        
        Args:
            redis_url: Redis connection URL
            ttl: Time to live for cache entries in seconds (default: 1 day)
            enabled: Whether the cache is enabled
        """
        self.redis_url = redis_url
        self.ttl = ttl
        self.enabled = enabled
        self.redis: Optional[Redis] = None
        
        logger.info(f"Initializing cache with Redis URL: {redis_url}, TTL: {ttl}, enabled: {enabled}")
    
    async def connect(self) -> bool:
        """
        Connect to Redis.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            self.redis = redis.asyncio.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
            return False
    
    async def get(self, phone: str, source: str) -> Optional[PhoneCheckResult]:
        """
        Get cached result for a phone number.
        
        Args:
            phone: Phone number
            source: Source of the check
            
        Returns:
            Optional[PhoneCheckResult]: Cached result or None if not found
        """
        if not self.enabled or not self.redis:
            if not await self.connect():
                return None
        
        try:
            key = CacheKeys.phone_check_key(phone, source)
            data = await self.redis.get(key)
            
            if not data:
                return None
            
            # Parse JSON data
            result_dict = json.loads(data)
            
            # Create PhoneCheckResult from dictionary
            return PhoneCheckResult(
                phone_number=result_dict["phone_number"],
                status=result_dict["status"],
                details=result_dict["details"],
                source=result_dict["source"]
            )
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    async def set(self, result: PhoneCheckResult) -> bool:
        """
        Cache a phone check result.
        
        Args:
            result: Phone check result to cache
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled or not self.redis:
            if not await self.connect():
                return False
        
        try:
            key = CacheKeys.phone_check_key(result.phone_number, result.source)
            
            # Convert result to dictionary
            result_dict = {
                "phone_number": result.phone_number,
                "status": result.status,
                "details": result.details,
                "source": result.source
            }
            
            # Convert to JSON and store
            await self.redis.set(key, json.dumps(result_dict), ex=self.ttl)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    async def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled or not self.redis:
            if not await self.connect():
                return False
        
        try:
            # Find all keys with the phone check prefix
            pattern = f"{CacheKeys.PHONE_CHECK_PREFIX}*"
            cursor = b"0"
            count = 0
            
            while cursor:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
                
                if keys:
                    await self.redis.delete(*keys)
                    count += len(keys)
                
                if cursor == b"0":
                    break
            
            logger.info(f"Cleared {count} cache entries")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        if not self.enabled or not self.redis:
            if not await self.connect():
                return {"enabled": False, "connected": False}
        
        try:
            # Find all keys with the phone check prefix
            pattern = f"{CacheKeys.PHONE_CHECK_PREFIX}*"
            cursor = b"0"
            count = 0
            
            while cursor:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
                count += len(keys)
                
                if cursor == b"0":
                    break
            
            # Get Redis info
            info = await self.redis.info()
            
            return {
                "enabled": self.enabled,
                "connected": True,
                "entries": count,
                "ttl": self.ttl,
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown")
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"enabled": self.enabled, "connected": False, "error": str(e)}


# Cache singleton instance
_cache_instance: Optional[PhoneCheckerCache] = None


def init_cache(redis_url: str, ttl: int = 86400, enabled: bool = True) -> PhoneCheckerCache:
    """
    Initialize the cache singleton.
    
    Args:
        redis_url: Redis connection URL
        ttl: Time to live for cache entries in seconds
        enabled: Whether the cache is enabled
        
    Returns:
        PhoneCheckerCache: Cache instance
    """
    global _cache_instance
    _cache_instance = PhoneCheckerCache(redis_url, ttl, enabled)
    return _cache_instance


def get_cache() -> PhoneCheckerCache:
    """
    Get the cache singleton instance.
    
    Returns:
        PhoneCheckerCache: Cache instance
        
    Raises:
        CacheError: If cache is not initialized
    """
    if _cache_instance is None:
        raise CacheError("Cache not initialized. Call init_cache first.")
    return _cache_instance
