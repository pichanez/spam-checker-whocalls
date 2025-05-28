#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Device interface abstraction for Android devices.
Provides a common interface for interacting with Android devices.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Union


class DeviceInterface(ABC):
    """Abstract interface for device interactions."""
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the device.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def launch_app(self, package: str, activity: str = "") -> bool:
        """
        Launch application on the device.
        
        Args:
            package: Application package name
            activity: Optional activity name to launch
            
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def close_app(self, package: str) -> bool:
        """
        Close application on the device.
        
        Args:
            package: Application package name
            
        Returns:
            bool: True if app closed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def click_element(self, locator: Dict[str, Any], timeout: int = 5) -> bool:
        """
        Click on UI element.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait for element
            
        Returns:
            bool: True if click was successful, False otherwise
        """
        pass

    @abstractmethod
    def press(self, key: Union[int, str]) -> bool:
        """
        Press key via name or key code.
        
        Args:
            locator: home, back, left, right, up, down, center, menu, search, enter,
            delete(or del), recent(recent apps), volume_up, volume_down,
            volume_mute, camera, power.
            
        Returns:
            bool: True if press key was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def input_text(self, locator: Dict[str, Any], text: str, timeout: int = 5) -> bool:
        """
        Input text into UI element.
        
        Args:
            locator: Dictionary with element locator
            text: Text to input
            timeout: Maximum time to wait for element
            
        Returns:
            bool: True if input was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def wait_for_element(self, locator: Dict[str, Any], timeout: int = 5) -> bool:
        """
        Wait for a UI element to appear.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait
            
        Returns:
            bool: True if element appeared, False otherwise
        """
        pass
    
    @abstractmethod
    def element_exists(self, locator: Dict[str, Any], timeout: int = 0) -> bool:
        """
        Check if a UI element exists.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait
            
        Returns:
            bool: True if element exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_element_text(self, locator: Dict[str, Any], timeout: int = 5) -> Optional[str]:
        """
        Get text from a UI element.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait for element
            
        Returns:
            Optional[str]: Text of the element or None if not found
        """
        pass
    
    @abstractmethod
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get device status information.
        
        Returns:
            Dict[str, Any]: Dictionary with device status information
        """
        pass
    
    @abstractmethod
    def screenshot(self, filename: Optional[str] = None) -> Optional[str]:
        """
        Take a screenshot of the device.
        
        Args:
            filename: Optional filename to save screenshot
            
        Returns:
            Optional[str]: Path to saved screenshot or None if failed
        """
        pass
    
    @abstractmethod
    def execute_shell(self, cmd: str) -> Tuple[str, str]:
        """
        Execute shell command on device.
        
        Args:
            cmd: Shell command to execute
            
        Returns:
            Tuple[str, str]: Tuple of (stdout, stderr)
        """
        pass
    
    @abstractmethod
    def restart(self) -> bool:
        """
        Restart the device connection.
        
        Returns:
            bool: True if restart successful, False otherwise
        """
        pass
