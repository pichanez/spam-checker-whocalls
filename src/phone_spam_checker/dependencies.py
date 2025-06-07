from typing import Dict
import asyncio
from fastapi import FastAPI, Request

from .config import settings
from .device_pool import DevicePool
from .distributed_pool import RedisDevicePool, RedisJobQueue
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore
from .job_manager import JobManager, SQLiteJobRepository, PostgresJobRepository

def init_app(app: FastAPI) -> None:
    """Create and store shared dependencies on the application."""
    if settings.pg_host:
        repo = PostgresJobRepository(settings.pg_dsn)
    else:
        repo = SQLiteJobRepository(settings.job_db_path)
    app.state.job_manager = JobManager(repo)

    redis_client = None
    if settings.use_redis:
        if redis is None:
            raise RuntimeError("redis package is required for distributed mode")
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=int(settings.redis_port),
            decode_responses=True,
        )
        app.state.redis_client = redis_client

    if settings.use_redis:
        job_queue: asyncio.Queue | RedisJobQueue = RedisJobQueue("job_queue", redis_client)  # type: ignore[arg-type]
    else:
        job_queue = asyncio.Queue()
    app.state.job_queue = job_queue

    devices_map = {
        "kaspersky": settings.kasp_devices,
        "truecaller": settings.tc_devices,
        "getcontact": settings.gc_devices,
        "tbank": [],
    }
    pools: Dict[str, DevicePool] = {}
    for svc, devs in devices_map.items():
        if settings.use_redis:
            pools[svc] = RedisDevicePool(f"pool:{svc}", devs, redis_client)  # type: ignore[arg-type]
        else:
            pools[svc] = DevicePool(devs)
    app.state.device_pools = pools


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def get_job_queue(request: Request) -> asyncio.Queue | RedisJobQueue:
    return request.app.state.job_queue


def get_device_pool(service: str, request: Request) -> DevicePool:
    return request.app.state.device_pools[service]
