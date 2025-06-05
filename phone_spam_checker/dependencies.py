from typing import Dict

from .config import settings
from .device_pool import DevicePool
from .job_manager import JobManager, SQLiteJobRepository, PostgresJobRepository

_job_manager: JobManager | None = None
_device_pools: Dict[str, DevicePool] = {}


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        if settings.pg_host:
            repo = PostgresJobRepository(settings.pg_dsn)
        else:
            repo = SQLiteJobRepository(settings.job_db_path)
        _job_manager = JobManager(repo)
    return _job_manager


def get_device_pool(service: str) -> DevicePool:
    global _device_pools
    pool = _device_pools.get(service)
    if pool is None:
        devices_map = {
            "kaspersky": settings.kasp_devices,
            "truecaller": settings.tc_devices,
            "getcontact": settings.gc_devices,
        }
        pool = DevicePool(devices_map[service])
        _device_pools[service] = pool
    return pool
