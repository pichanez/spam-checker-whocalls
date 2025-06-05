import asyncio
import json
import threading
from typing import List, Tuple

from .exceptions import JobAlreadyRunningError

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


class RedisDevicePool:
    """Distributed device pool backed by Redis lists."""

    def __init__(self, name: str, devices: List[str], client: "redis.Redis") -> None:
        if redis is None:
            raise RuntimeError("redis package is required for RedisDevicePool")
        self._name = name
        self._redis = client
        self._local = threading.local()
        if devices and not self._redis.exists(name):
            self._redis.rpush(name, *devices)

    def acquire(self, timeout: int = 1) -> str:
        result = self._redis.blpop(self._name, timeout=timeout)
        if result is None:
            raise JobAlreadyRunningError("No free device")
        value = result[1]
        if isinstance(value, bytes):
            value = value.decode()
        return value

    def release(self, device: str) -> None:
        self._redis.rpush(self._name, device)

    def __len__(self) -> int:
        return int(self._redis.llen(self._name))

    # ------------------------------------------------------------------
    # context manager support
    # ------------------------------------------------------------------
    def __enter__(self) -> str:
        device = self.acquire()
        stack = getattr(self._local, "stack", None)
        if stack is None:
            stack = []
            self._local.stack = stack
        stack.append(device)
        return device

    def __exit__(self, exc_type, exc, tb) -> None:
        stack = getattr(self._local, "stack", [])
        if not stack:
            return
        device = stack.pop()
        self.release(device)


class RedisJobQueue:
    """Async job queue stored in Redis."""

    def __init__(self, name: str, client: "redis.Redis") -> None:
        if redis is None:
            raise RuntimeError("redis package is required for RedisJobQueue")
        self._name = name
        self._redis = client
        self._pending = 0
        self._event = asyncio.Event()
        self._event.set()
        self._lock = asyncio.Lock()

    async def put(self, item: Tuple[str, List[str], str]) -> None:
        data = json.dumps(item)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._redis.rpush, self._name, data)
        async with self._lock:
            self._pending += 1
            self._event.clear()

    async def get(self) -> Tuple[str, List[str], str]:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: self._redis.blpop(self._name)[1]
        )
        job_id, numbers, service = json.loads(data)
        return job_id, numbers, service

    def task_done(self) -> None:
        async def _update() -> None:
            async with self._lock:
                self._pending -= 1
                if self._pending <= 0:
                    self._event.set()

        asyncio.create_task(_update())

    async def join(self) -> None:
        await self._event.wait()
