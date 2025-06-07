import threading
from typing import List

from .exceptions import JobAlreadyRunningError

class DevicePool:
    """Simple synchronized pool for allocating devices."""

    def __init__(self, devices: List[str]):
        self._lock = threading.Lock()
        self._devices = list(devices)
        self._local = threading.local()

    def acquire(self) -> str:
        with self._lock:
            if not self._devices:
                raise JobAlreadyRunningError("No free device")
            return self._devices.pop()

    def release(self, device: str) -> None:
        with self._lock:
            self._devices.append(device)

    def __len__(self) -> int:
        with self._lock:
            return len(self._devices)

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
