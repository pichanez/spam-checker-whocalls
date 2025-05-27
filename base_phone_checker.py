#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base abstract class for phone number checkers.
Provides common interface and functionality for all checker implementations.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Type, TypeVar

import uiautomator2 as u2
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("phone_checker")


@dataclass
class PhoneCheckResult:
    """Unified result model for all phone checkers."""
    phone_number: str
    status: str  # "Safe", "Spam", "Not in database", "Error", "Unknown"
    details: str = ""
    source: str = ""  # Name of the checker that provided this result


class PhoneCheckerError(Exception):
    """Base exception for all phone checker errors."""
    pass


class DeviceConnectionError(PhoneCheckerError):
    """Error when connecting to Android device."""
    pass


class AppLaunchError(PhoneCheckerError):
    """Error when launching the application."""
    pass


class UIInteractionError(PhoneCheckerError):
    """Error when interacting with UI elements."""
    pass


T = TypeVar('T', bound='BasePhoneChecker')


class BasePhoneChecker(ABC):
    """Abstract base class for phone number checkers."""

    def __init__(self, device: str):
        """
        Initialize the checker with device connection.
        
        Args:
            device: Android device identifier (e.g., "127.0.0.1:5555")
        """
        self.device_id = device
        self.app_package = ""  # To be set by subclasses
        self.app_activity = ""  # To be set by subclasses
        self.source_name = self.__class__.__name__
        
        logger.info(f"Connecting to device {device}")
        try:
            self.d = u2.connect(device)
            # Try to wake up and unlock the device
            for fn in ("screen_on", "unlock"):
                try:
                    getattr(self.d, fn)()
                except Exception:
                    pass
        except Exception as e:
            raise DeviceConnectionError(f"Failed to connect to device {device}: {e}") from e

    @abstractmethod
    def launch_app(self) -> bool:
        """
        Launch the application and prepare it for number checking.
        
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        pass

    @abstractmethod
    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number and return the result.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        pass

    def close_app(self) -> None:
        """Close the application."""
        logger.info(f"Closing {self.app_package}")
        try:
            self.d.app_stop(self.app_package)
        except Exception as e:
            logger.error(f"Error closing app: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(UIInteractionError)
    )
    def click_element(self, locator: Dict[str, str], timeout: int = 5) -> bool:
        """
        Click on a UI element with retry mechanism.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait for element
            
        Returns:
            bool: True if click was successful
            
        Raises:
            UIInteractionError: If element not found or click failed
        """
        element = self.d(**locator)
        if not element.exists(timeout=timeout):
            raise UIInteractionError(f"Element not found: {locator}")
        try:
            element.click()
            return True
        except Exception as e:
            raise UIInteractionError(f"Failed to click element {locator}: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(UIInteractionError)
    )
    def input_text(self, locator: Dict[str, str], text: str, timeout: int = 5) -> bool:
        """
        Input text into a UI element with retry mechanism.
        
        Args:
            locator: Dictionary with element locator
            text: Text to input
            timeout: Maximum time to wait for element
            
        Returns:
            bool: True if input was successful
            
        Raises:
            UIInteractionError: If element not found or input failed
        """
        element = self.d(**locator)
        if not element.exists(timeout=timeout):
            raise UIInteractionError(f"Element not found: {locator}")
        try:
            element.click()
            element.clear_text()
            element.set_text(text)
            return True
        except Exception as e:
            raise UIInteractionError(f"Failed to input text to element {locator}: {e}") from e

    def wait_for_element(self, locator: Dict[str, str], timeout: int = 5) -> bool:
        """
        Wait for a UI element to appear.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait
            
        Returns:
            bool: True if element appeared, False otherwise
        """
        return self.d(**locator).wait(timeout=timeout)

    def element_exists(self, locator: Dict[str, str], timeout: int = 0) -> bool:
        """
        Check if a UI element exists.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait
            
        Returns:
            bool: True if element exists, False otherwise
        """
        return self.d(**locator).exists(timeout=timeout)

    def get_element_text(self, locator: Dict[str, str], timeout: int = 5) -> Optional[str]:
        """
        Get text from a UI element.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait for element
            
        Returns:
            str: Text of the element or None if not found
        """
        element = self.d(**locator)
        if not element.exists(timeout=timeout):
            return None
        try:
            return element.get_text()
        except Exception as e:
            logger.error(f"Failed to get text from element {locator}: {e}")
            return None

    @classmethod
    def create(cls: Type[T], device: str) -> T:
        """
        Factory method to create a checker instance.
        
        Args:
            device: Android device identifier
            
        Returns:
            BasePhoneChecker: Instance of the checker
        """
        return cls(device)


class PhoneCheckerFactory:
    """Factory for creating appropriate phone checkers based on phone number."""
    
    @staticmethod
    def get_checker_for_number(phone: str, config: Dict[str, Any]) -> BasePhoneChecker:
        """
        Get appropriate checker for a phone number.
        
        Args:
            phone: Phone number to check
            config: Configuration with device IDs
            
        Returns:
            BasePhoneChecker: Appropriate checker instance
        """
        # Import here to avoid circular imports
        from kaspersky_phone_checker import KasperskyWhoCallsChecker
        from truecaller_phone_checker import TruecallerChecker
        from getcontact_phone_checker import GetContactChecker
        
        # For Russian numbers, prefer Kaspersky
        if phone.startswith("+7") or phone.startswith("7"):
            return KasperskyWhoCallsChecker(config["kaspersky_device"])
        
        # For other numbers, use Truecaller
        return TruecallerChecker(config["truecaller_device"])
    
    @staticmethod
    def get_all_checkers(config: Dict[str, Any]) -> Dict[str, BasePhoneChecker]:
        """
        Get all available checkers.
        
        Args:
            config: Configuration with device IDs
            
        Returns:
            Dict[str, BasePhoneChecker]: Dictionary of checker name to instance
        """
        # Import here to avoid circular imports
        from kaspersky_phone_checker import KasperskyWhoCallsChecker
        from truecaller_phone_checker import TruecallerChecker
        from getcontact_phone_checker import GetContactChecker
        
        return {
            "kaspersky": KasperskyWhoCallsChecker(config["kaspersky_device"]),
            "truecaller": TruecallerChecker(config["truecaller_device"]),
            "getcontact": GetContactChecker(config["getcontact_device"])
        }


def read_phone_list(path: str) -> List[str]:
    """
    Read phone numbers from a file.
    
    Args:
        path: Path to the file with phone numbers
        
    Returns:
        List[str]: List of phone numbers
    """
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number format.
    
    Args:
        phone: Phone number in any format
        
    Returns:
        str: Normalized phone number
    """
    # Remove all non-digit characters
    digits_only = ''.join(c for c in phone if c.isdigit())
    
    # Add + prefix if missing
    if not phone.startswith('+'):
        if digits_only.startswith('7') and len(digits_only) == 11:
            return f"+{digits_only}"
        elif len(digits_only) == 10 and not digits_only.startswith('7'):
            return f"+7{digits_only}"
    
    return phone
