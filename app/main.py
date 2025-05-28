#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application module for the phone-spam-checker.
"""

import os
import logging
import asyncio
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from prometheus_client import start_http_server

from app.api.routes import router
from app.services.phone_checker_service import PhoneCheckerService
from app.repositories.cache_repository import init_cache, get_cache
from app.infrastructure.device.android_device import AndroidDevice

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("phone_checker.main")

# Create FastAPI app
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

# Include API routes
app.include_router(router)

# Device configuration
DEVICE_CONFIG = {
    "kaspersky": f"{os.getenv('KASP_ADB_HOST', '127.0.0.1')}:{os.getenv('KASP_ADB_PORT', '5555')}",
    "truecaller": f"{os.getenv('TC_ADB_HOST', '127.0.0.1')}:{os.getenv('TC_ADB_PORT', '5556')}",
    "getcontact": f"{os.getenv('GC_ADB_HOST', '127.0.0.1')}:{os.getenv('GC_ADB_PORT', '5557')}"
}

# Global service instance
phone_checker_service: PhoneCheckerService = None


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global phone_checker_service
    
    # Initialize cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl = int(os.getenv("CACHE_TTL", "86400"))
    cache_enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    
    init_cache(redis_url, cache_ttl, cache_enabled)
    cache = get_cache()
    
    # Initialize devices
    devices = {}
    for name, device_id in DEVICE_CONFIG.items():
        devices[name] = AndroidDevice(device_id)
    
    # Initialize service
    phone_checker_service = PhoneCheckerService(cache, devices)
    
    # Start background tasks
    asyncio.create_task(phone_checker_service.cleanup_jobs(
        interval_seconds=int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))
    ))
    
    # Start metrics server
    try:
        metrics_port = int(os.getenv("METRICS_PORT", "8001"))
        start_http_server(metrics_port)
        logger.info(f"Started Prometheus metrics server on port {metrics_port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")


# Customize OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    # Apply security to all endpoints except /health
    for path, path_item in openapi_schema["paths"].items():
        if path != "/health":
            for method in path_item:
                path_item[method]["security"] = [{"ApiKeyAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
