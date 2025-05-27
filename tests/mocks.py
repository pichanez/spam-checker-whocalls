#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock implementations for testing phone checker modules.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock

from base_phone_checker import PhoneCheckResult

# Configure logger
logger = logging.getLogger("phone_checker.mocks")


class MockElement:
    """Mock for uiautomator2 UI element."""
    
    def __init__(self, locator: Dict[str, str], exists_result: bool = True, text: str = "Mock Text"):
        """
        Initialize mock element.
        
        Args:
            locator: Element locator dictionary
            exists_result: Whether element exists
            text: Text to return from get_text()
        """
        self.locator = locator
        self.exists_result = exists_result
        self.text_result = text
        
        # Create mocks for methods
        self.click = MagicMock(return_value=True)
        self.clear_text = MagicMock(return_value=True)
        self.set_text = MagicMock(return_value=True)
    
    def wait(self, timeout: int = 0) -> bool:
        """Mock wait for element."""
        return self.exists_result
    
    def exists(self, timeout: int = 0) -> bool:
        """Mock check if element exists."""
        return self.exists_result
    
    def get_text(self) -> str:
        """Mock get element text."""
        if 'text' in self.locator:
            return self.locator['text']
        return self.text_result


class MockDevice:
    """Mock for uiautomator2.Device."""
    
    def __init__(self, device_id: str, elements_config: Optional[Dict[str, Any]] = None):
        """
        Initialize mock device.
        
        Args:
            device_id: Device identifier
            elements_config: Configuration for UI elements
        """
        self.device_id = device_id
        self.elements_config = elements_config or {}
        self.info = {
            "screenOn": True,
            "screenLocked": False,
        }
        
        # Create mocks for methods
        self.app_start = MagicMock(return_value=True)
        self.app_stop = MagicMock(return_value=True)
        self.press = MagicMock(return_value=True)
        self.screen_on = MagicMock(return_value=True)
        self.unlock = MagicMock(return_value=True)
        
        # Mock shell command results
        self.shell_results = {
            "dumpsys battery | grep level": "level: 85",
            "ps | grep -e com.truecaller -e com.kaspersky": "com.kaspersky.who_calls",
        }
    
    def __call__(self, **locator) -> MockElement:
        """Create mock element for given locator."""
        locator_str = json.dumps(locator)
        
        # Check if we have specific configuration for this locator
        for pattern, config in self.elements_config.items():
            if pattern in locator_str:
                return MockElement(
                    locator,
                    exists_result=config.get("exists", True),
                    text=config.get("text", "Mock Text")
                )
        
        # Default element
        return MockElement(locator)
    
    def shell(self, cmd: str) -> Any:
        """Mock shell command execution."""
        result = MagicMock()
        result.output = self.shell_results.get(cmd, "")
        return result


class MockCache:
    """Mock for PhoneCheckerCache."""
    
    def __init__(self, predefined_results: Optional[Dict[str, PhoneCheckResult]] = None):
        """
        Initialize mock cache.
        
        Args:
            predefined_results: Dictionary of phone number to result
        """
        self.cache = predefined_results or {}
        self.is_available = True
    
    async def get(self, phone: str, source: Optional[str] = None) -> Optional[PhoneCheckResult]:
        """Get cached result."""
        key = f"{phone}:{source}" if source else phone
        return self.cache.get(key)
    
    async def set(self, result: PhoneCheckResult, ttl: Optional[int] = None) -> bool:
        """Cache a result."""
        key = f"{result.phone_number}:{result.source}" if result.source else result.phone_number
        self.cache[key] = result
        return True
    
    async def delete(self, phone: str, source: Optional[str] = None) -> bool:
        """Delete cached result."""
        key = f"{phone}:{source}" if source else phone
        if key in self.cache:
            del self.cache[key]
        return True
    
    async def get_multiple(self, phones: List[str], source: Optional[str] = None) -> Dict[str, PhoneCheckResult]:
        """Get multiple cached results."""
        results = {}
        for phone in phones:
            key = f"{phone}:{source}" if source else phone
            if key in self.cache:
                results[phone] = self.cache[key]
        return results
    
    async def set_multiple(self, results: List[PhoneCheckResult], ttl: Optional[int] = None) -> bool:
        """Cache multiple results."""
        for result in results:
            key = f"{result.phone_number}:{result.source}" if result.source else result.phone_number
            self.cache[key] = result
        return True
    
    async def clear_all(self) -> bool:
        """Clear all cached results."""
        self.cache.clear()
        return True


def create_mock_device_with_config(device_id: str, config: Dict[str, Any]) -> MockDevice:
    """
    Create a mock device with specific configuration.
    
    Args:
        device_id: Device identifier
        config: Configuration dictionary
        
    Returns:
        MockDevice: Configured mock device
    """
    # Default element configurations
    default_elements = {
        "Check number": {"exists": True, "text": "Check number"},
        "android.widget.EditText": {"exists": True, "text": ""},
        "Check": {"exists": True, "text": "Check"},
        "No feedback": {"exists": False, "text": "No feedback on the number"},
        "SPAM": {"exists": False, "text": "SPAM!"},
        "useful": {"exists": True, "text": "This number is useful"},
        "searchBarLabel": {"exists": True, "text": "Search numbers..."},
        "search_field": {"exists": True, "text": ""},
        "searchWeb": {"exists": False, "text": "SEARCH THE WEB"},
        "nameOrNumber": {"exists": True, "text": "John Doe"},
        "numberDetails": {"exists": True, "text": "Mobile, New York"},
        "phoneNumber": {"exists": True, "text": "+1234567890"},
        "searchhint": {"exists": True, "text": "Search by number"},
        "notFoundDisplayNameText": {"exists": False, "text": "Not found"},
        "displayNameText": {"exists": True, "text": "John Smith"},
        "Spam": {"exists": False, "text": "Spam"},
        "ConfirmationDialogNegativeButton": {"exists": False, "text": "CANCEL"},
        "dialog.privateModeSettings.title": {"exists": False, "text": "Private Mode Settings"},
    }
    
    # Override with provided config
    elements_config = {**default_elements, **config.get("elements", {})}
    
    # Create device
    device = MockDevice(device_id, elements_config)
    
    # Override shell results if provided
    if "shell_results" in config:
        device.shell_results.update(config["shell_results"])
    
    # Override device info if provided
    if "info" in config:
        device.info.update(config["info"])
    
    return device


def create_predefined_cache_results() -> Dict[str, PhoneCheckResult]:
    """
    Create predefined cache results for testing.
    
    Returns:
        Dict[str, PhoneCheckResult]: Dictionary of phone number to result
    """
    return {
        "+79123456789:Kaspersky": PhoneCheckResult(
            phone_number="+79123456789",
            status="Safe",
            details="This number is useful",
            source="Kaspersky"
        ),
        "+79123456789": PhoneCheckResult(
            phone_number="+79123456789",
            status="Safe",
            details="This number is useful",
            source="Kaspersky"
        ),
        "+12025550108:Truecaller": PhoneCheckResult(
            phone_number="+12025550108",
            status="Spam",
            details="Reported as spam by 5 users",
            source="Truecaller"
        ),
        "+12025550108": PhoneCheckResult(
            phone_number="+12025550108",
            status="Spam",
            details="Reported as spam by 5 users",
            source="Truecaller"
        ),
        "+12025550109:GetContact": PhoneCheckResult(
            phone_number="+12025550109",
            status="Not in database",
            details="No result found!",
            source="GetContact"
        ),
        "+12025550109": PhoneCheckResult(
            phone_number="+12025550109",
            status="Not in database",
            details="No result found!",
            source="GetContact"
        ),
    }
