#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Type protocols for the phone-spam-checker application.
"""

from typing import Protocol, Dict, Any, Optional, Tuple


class DeviceProtocol(Protocol):
    """Protocol for device interactions."""
    
    def connect(self) -> bool:
        """Connect to the device."""
        ...
    
    def launch_app(self, package: str, activity: str = "") -> bool:
        """Launch application on the device."""
        ...
    
    def close_app(self, package: str) -> bool:
        """Close application on the device."""
        ...
    
    def click_element(self, locator: Dict[str, Any], timeout: int = 5) -> bool:
        """Click on UI element."""
        ...
    
    def input_text(self, locator: Dict[str, Any], text: str, timeout: int = 5) -> bool:
        """Input text into UI element."""
        ...
    
    def wait_for_element(self, locator: Dict[str, Any], timeout: int = 5) -> bool:
        """Wait for a UI element to appear."""
        ...
    
    def element_exists(self, locator: Dict[str, Any], timeout: int = 0) -> bool:
        """Check if a UI element exists."""
        ...
    
    def get_element_text(self, locator: Dict[str, Any], timeout: int = 5) -> Optional[str]:
        """Get text from a UI element."""
        ...
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get device status information."""
        ...
    
    def screenshot(self, filename: Optional[str] = None) -> Optional[str]:
        """Take a screenshot of the device."""
        ...
    
    def execute_shell(self, cmd: str) -> Tuple[str, str]:
        """Execute shell command on device."""
        ...
    
    def restart(self) -> bool:
        """Restart the device connection."""
        ...


class CacheProtocol(Protocol):
    """Protocol for cache operations."""
    
    async def connect(self) -> bool:
        """Connect to cache backend."""
        ...
    
    async def get(self, phone: str, source: str) -> Optional[Any]:
        """Get cached result for a phone number."""
        ...
    
    async def set(self, result: Any) -> bool:
        """Cache a phone check result."""
        ...
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        ...
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        ...


class PhoneCheckerProtocol(Protocol):
    """Protocol for phone checker strategies."""
    
    def can_handle(self, phone_number: str) -> bool:
        """Check if this strategy can handle the given phone number."""
        ...
    
    def launch_app(self) -> bool:
        """Launch the application and prepare it for number checking."""
        ...
    
    def check_number(self, phone: str) -> Any:
        """Check a phone number and return the result."""
        ...
    
    def close_app(self) -> None:
        """Close the application."""
        ...
