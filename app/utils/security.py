#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security middleware and utilities for the phone-spam-checker application.
"""

import os
import time
import logging
import hashlib
import secrets
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta

from fastapi import Request, Response, HTTPException, Depends
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from redis.asyncio import Redis

from app.utils.exceptions import AuthenticationError, RateLimitError

# Configure logging
logger = logging.getLogger("phone_checker.security")


class APIKeyAuth:
    """API key authentication handler."""
    
    def __init__(self, api_key_name: str = "X-API-Key", api_key: Optional[str] = None):
        """
        Initialize API key authentication.
        
        Args:
            api_key_name: Name of the API key header
            api_key: API key value (if None, will be read from environment)
        """
        self.api_key_name = api_key_name
        self.api_key = api_key or os.getenv("API_KEY", "")
        self.api_key_header = APIKeyHeader(name=api_key_name, auto_error=False)
    
    async def __call__(self, request: Request) -> str:
        """
        Validate API key.
        
        Args:
            request: FastAPI request
            
        Returns:
            str: Validated API key
            
        Raises:
            HTTPException: If API key is invalid
        """
        api_key = await self.api_key_header(request)
        
        if not self.api_key or api_key != self.api_key:
            logger.warning(f"Invalid API key attempt from {request.client.host}")
            raise HTTPException(status_code=403, detail="Forbidden")
        
        return api_key


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(
        self,
        redis: Redis,
        limit: int = 100,
        window: int = 60,
        key_prefix: str = "ratelimit:"
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis: Redis client
            limit: Maximum number of requests per window
            window: Time window in seconds
            key_prefix: Prefix for Redis keys
        """
        self.redis = redis
        self.limit = limit
        self.window = window
        self.key_prefix = key_prefix
    
    async def is_rate_limited(self, key: str) -> bool:
        """
        Check if a key is rate limited.
        
        Args:
            key: Rate limit key (usually IP address or API key)
            
        Returns:
            bool: True if rate limited, False otherwise
        """
        redis_key = f"{self.key_prefix}{key}"
        
        # Get current count
        count = await self.redis.get(redis_key)
        
        if count is None:
            # First request, set to 1 with expiry
            await self.redis.set(redis_key, 1, ex=self.window)
            return False
        
        count = int(count)
        
        if count >= self.limit:
            logger.warning(f"Rate limit exceeded for {key}: {count}/{self.limit}")
            return True
        
        # Increment count
        await self.redis.incr(redis_key)
        return False
    
    async def get_remaining(self, key: str) -> Dict[str, Any]:
        """
        Get remaining requests information.
        
        Args:
            key: Rate limit key
            
        Returns:
            Dict[str, Any]: Rate limit information
        """
        redis_key = f"{self.key_prefix}{key}"
        
        # Get current count and TTL
        count = await self.redis.get(redis_key)
        ttl = await self.redis.ttl(redis_key)
        
        if count is None:
            return {
                "limit": self.limit,
                "remaining": self.limit,
                "reset": int(time.time()) + self.window
            }
        
        return {
            "limit": self.limit,
            "remaining": max(0, self.limit - int(count)),
            "reset": int(time.time()) + (ttl if ttl > 0 else self.window)
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""
    
    def __init__(
        self,
        app: ASGIApp,
        limiter: RateLimiter,
        exclude_paths: Optional[List[str]] = None
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            app: ASGI application
            limiter: Rate limiter instance
            exclude_paths: List of paths to exclude from rate limiting
        """
        super().__init__(app)
        self.limiter = limiter
        self.exclude_paths = exclude_paths or ["/health"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware or endpoint
            
        Returns:
            Response: FastAPI response
        """
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Get client identifier (API key if present, otherwise IP)
        client_id = request.headers.get("X-API-Key", request.client.host)
        
        # Check rate limit
        is_limited = await self.limiter.is_rate_limited(client_id)
        if is_limited:
            # Get rate limit info
            rate_info = await self.limiter.get_remaining(client_id)
            
            # Return 429 Too Many Requests
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                    "Retry-After": str(rate_info["reset"] - int(time.time()))
                }
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        rate_info = await self.limiter.get_remaining(client_id)
        
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
        
        return response


class AuditLogger:
    """Logger for audit events."""
    
    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file
        """
        self.logger = logging.getLogger("phone_checker.audit")
        
        if log_file:
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter(
                "%(asctime)s [AUDIT] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_event(
        self,
        event_type: str,
        user: str,
        resource: str,
        action: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            user: User identifier
            resource: Resource being accessed
            action: Action being performed
            status: Status of the action
            details: Additional details
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user": user,
            "resource": resource,
            "action": action,
            "status": status
        }
        
        if details:
            event["details"] = details
        
        self.logger.info(f"{event}")


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for audit logging."""
    
    def __init__(
        self,
        app: ASGIApp,
        audit_logger: AuditLogger,
        exclude_paths: Optional[List[str]] = None
    ):
        """
        Initialize audit middleware.
        
        Args:
            app: ASGI application
            audit_logger: Audit logger instance
            exclude_paths: List of paths to exclude from audit logging
        """
        super().__init__(app)
        self.audit_logger = audit_logger
        self.exclude_paths = exclude_paths or ["/health"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with audit logging.
        
        Args:
            request: FastAPI request
            call_next: Next middleware or endpoint
            
        Returns:
            Response: FastAPI response
        """
        # Skip audit logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Get client identifier
        client_id = request.headers.get("X-API-Key", request.client.host)
        
        # Log request
        self.audit_logger.log_event(
            event_type="api_request",
            user=client_id,
            resource=request.url.path,
            action=request.method,
            status="started",
            details={
                "query_params": str(request.query_params),
                "client_host": request.client.host,
                "user_agent": request.headers.get("User-Agent", "")
            }
        )
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log response
        self.audit_logger.log_event(
            event_type="api_response",
            user=client_id,
            resource=request.url.path,
            action=request.method,
            status=str(response.status_code),
            details={
                "duration_ms": round(duration * 1000, 2),
                "content_type": response.headers.get("Content-Type", "")
            }
        )
        
        return response


def generate_api_key() -> str:
    """
    Generate a secure API key.
    
    Returns:
        str: Secure API key
    """
    return secrets.token_urlsafe(32)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password with a salt.
    
    Args:
        password: Password to hash
        salt: Salt for hashing (if None, a new salt will be generated)
        
    Returns:
        tuple[str, str]: Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Hash password with salt
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()
    
    return hashed, salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        password: Password to verify
        hashed_password: Hashed password
        salt: Salt used for hashing
        
    Returns:
        bool: True if password matches hash, False otherwise
    """
    new_hash, _ = hash_password(password, salt)
    return new_hash == hashed_password
