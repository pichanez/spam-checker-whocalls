import threading
from typing import List

from .exceptions import JobAlreadyRunningError

class DevicePool:
    """Simple synchronized pool for allocating devices."""

    def __init__(self, devices: List[str]):
        self._lock = threading.Lock()
        self._devices = list(devices)

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
