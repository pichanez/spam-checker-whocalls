from typing import Dict, Any
import asyncio

from .config import settings
from .device_pool import DevicePool
from .distributed_pool import RedisDevicePool, RedisJobQueue
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore
from .job_manager import JobManager, SQLiteJobRepository, PostgresJobRepository

_job_manager: JobManager | None = None
_device_pools: Dict[str, DevicePool] = {}
_job_queue: asyncio.Queue | RedisJobQueue | None = None
_redis_client: Any | None = None  # redis.Redis when available


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        if settings.pg_host:
            repo = PostgresJobRepository(settings.pg_dsn)
        else:
            repo = SQLiteJobRepository(settings.job_db_path)
        _job_manager = JobManager(repo)
    return _job_manager


def _get_redis() -> "redis.Redis":
    global _redis_client
    if _redis_client is None:
        if redis is None:
            raise RuntimeError("redis package is required for distributed mode")
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=int(settings.redis_port),
            decode_responses=True,
        )
    return _redis_client


def get_device_pool(service: str) -> DevicePool:
    global _device_pools
    pool = _device_pools.get(service)
    if pool is None:
        devices_map = {
            "kaspersky": settings.kasp_devices,
            "truecaller": settings.tc_devices,
            "getcontact": settings.gc_devices,
        }
        if settings.use_redis:
            client = _get_redis()
            pool = RedisDevicePool(f"pool:{service}", devices_map[service], client)
        else:
            pool = DevicePool(devices_map[service])
        _device_pools[service] = pool
    return pool


def get_job_queue() -> asyncio.Queue | RedisJobQueue:
    global _job_queue
    if _job_queue is None:
        if settings.use_redis:
            client = _get_redis()
            _job_queue = RedisJobQueue("job_queue", client)
        else:
            _job_queue = asyncio.Queue()
    return _job_queue
