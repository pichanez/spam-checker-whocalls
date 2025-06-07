from abc import ABC, abstractmethod
from .models import PhoneCheckResult


class PhoneChecker(ABC):
    """Abstract interface for phone number checkers."""

    def __init__(self, device: str) -> None:
        self.device = device

    @abstractmethod
    def launch_app(self) -> bool:
        """Launch application on the device."""

    @abstractmethod
    def close_app(self) -> None:
        """Force close the application."""

    @abstractmethod
    def check_number(self, phone: str) -> PhoneCheckResult:
        """Check a single phone number and return the result."""
