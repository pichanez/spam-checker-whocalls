import logging

from ..device_client import AndroidDeviceClient
from ..domain.phone_checker import PhoneChecker

logger = logging.getLogger(__name__)


class AndroidAppChecker(PhoneChecker):
    """Base class for checkers running on Android devices."""

    def __init__(self, device: str) -> None:
        super().__init__(device)
        self.client = AndroidDeviceClient(device)
        self.d = self.client.d

