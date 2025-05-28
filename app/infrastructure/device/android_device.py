#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android device implementation using uiautomator2.
"""

import logging
import subprocess
from typing import Dict, Any, Optional, Tuple, Union

import uiautomator2 as u2
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from app.infrastructure.device.device_interface import DeviceInterface
from app.utils.exceptions import DeviceConnectionError, UIInteractionError

# Configure logging
logger = logging.getLogger("phone_checker.device")


class AndroidDevice(DeviceInterface):
    """Implementation of DeviceInterface for Android devices using uiautomator2."""
    
    def __init__(self, device_id: str):
        """
        Initialize the Android device.
        
        Args:
            device_id: Android device identifier (e.g., "127.0.0.1:5555")
        """
        self.device_id = device_id
        self.d = None
        logger.info(f"Initializing Android device {device_id}")
    
    def connect(self) -> bool:
        """
        Connect to the Android device.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to device {self.device_id}")
            self.d = u2.connect(self.device_id)
            
            # Try to wake up and unlock the device
            for fn in ("screen_on", "unlock"):
                try:
                    getattr(self.d, fn)()
                except Exception as e:
                    logger.warning(f"Failed to {fn}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to device {self.device_id}: {e}")
            raise DeviceConnectionError(f"Failed to connect to device {self.device_id}: {e}") from e
    
    def launch_app(self, package: str, activity: str = "") -> bool:
        """
        Launch application on the device.
        
        Args:
            package: Application package name
            activity: Optional activity name to launch
            
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        if not self.d:
            if not self.connect():
                return False
        else:
            return True
        
        try:
            logger.info(f"Launching app {package}")
            if activity:
                self.d.app_start(package, activity)
            else:
                self.d.app_start(package)
            return True
        except Exception as e:
            logger.error(f"Failed to launch app {package}: {e}")
            return False
    
    def close_app(self, package: str) -> bool:
        """
        Close application on the device.
        
        Args:
            package: Application package name
            
        Returns:
            bool: True if app closed successfully, False otherwise
        """
        if not self.d:
            return False
        
        try:
            logger.info(f"Closing app {package}")
            self.d.app_stop(package)
            return True
        except Exception as e:
            logger.error(f"Error closing app {package}: {e}")
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(UIInteractionError)
    )
    def click_element(self, locator: Dict[str, Any], timeout: int = 5) -> bool:
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
        if not self.d:
            if not self.connect():
                return False
        
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
    def press(self, key: Union[int, str]) -> bool:
        """
        Press key via name with retry mechanism.
        
        Args:
            key: home, back, left, right, up, down, center, menu, search, enter,
            delete(or del), recent(recent apps), volume_up, volume_down,
            volume_mute, camera, power.
            
        Returns:
            bool: True if press key was successful
            
        Raises:
            UIInteractionError: If element not found or click failed
        """
        if not self.d:
            if not self.connect():
                return False
        try:
            logging.debug(f"Pressing key {key}")
            self.d.press(key)
            return True
        except Exception as e:
            raise UIInteractionError(f"Failed to press key {key}: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(UIInteractionError)
    )
    def input_text(self, locator: Dict[str, Any], text: str, timeout: int = 5) -> bool:
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
        if not self.d:
            if not self.connect():
                return False
        
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
    
    def wait_for_element(self, locator: Dict[str, Any], timeout: int = 5) -> bool:
        """
        Wait for a UI element to appear.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait
            
        Returns:
            bool: True if element appeared, False otherwise
        """
        if not self.d:
            if not self.connect():
                return False
        
        return self.d(**locator).wait(timeout=timeout)
    
    def element_exists(self, locator: Dict[str, Any], timeout: int = 0) -> bool:
        """
        Check if a UI element exists.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait
            
        Returns:
            bool: True if element exists, False otherwise
        """
        if not self.d:
            if not self.connect():
                return False
        
        return self.d(**locator).exists(timeout=timeout)
    
    def get_element_text(self, locator: Dict[str, Any], timeout: int = 5) -> Optional[str]:
        """
        Get text from a UI element.
        
        Args:
            locator: Dictionary with element locator
            timeout: Maximum time to wait for element
            
        Returns:
            Optional[str]: Text of the element or None if not found
        """
        if not self.d:
            if not self.connect():
                return None
        
        element = self.d(**locator)
        if not element.exists(timeout=timeout):
            return None
        try:
            return element.get_text()
        except Exception as e:
            logger.error(f"Failed to get text from element {locator}: {e}")
            return None
    
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get device status information.
        
        Returns:
            Dict[str, Any]: Dictionary with device status information
        """
        if not self.d:
            try:
                self.connect()
            except Exception as e:
                return {
                    "connected": False,
                    "error": str(e)
                }
        
        try:
            info = self.d.info
            
            # Get battery info
            battery_output = self.d.shell("dumpsys battery | grep level").output.strip()
            battery_level = battery_output.split(":")[-1].strip() if battery_output else "Unknown"
            
            # Check running apps
            apps_output = self.d.shell("ps | grep -e com.truecaller -e com.kaspersky -e app.source.getcontact").output.strip()
            
            return {
                "connected": True,
                "screen_on": info.get("screenOn", False),
                "unlocked": not info.get("screenLocked", True),
                "battery": f"{battery_level}%",
                "running_apps": apps_output or "None",
                "error": None
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
    
    def screenshot(self, filename: Optional[str] = None) -> Optional[str]:
        """
        Take a screenshot of the device.
        
        Args:
            filename: Optional filename to save screenshot
            
        Returns:
            Optional[str]: Path to saved screenshot or None if failed
        """
        if not self.d:
            if not self.connect():
                return None
        
        try:
            return self.d.screenshot(filename)
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    def execute_shell(self, cmd: str) -> Tuple[str, str]:
        """
        Execute shell command on device.
        
        Args:
            cmd: Shell command to execute
            
        Returns:
            Tuple[str, str]: Tuple of (stdout, stderr)
        """
        if not self.d:
            if not self.connect():
                return ("", "Device not connected")
        
        try:
            result = self.d.shell(cmd)
            return (result.output, "")
        except Exception as e:
            logger.error(f"Failed to execute shell command: {e}")
            return ("", str(e))
    
    def restart(self) -> bool:
        """
        Restart the device connection.
        
        Returns:
            bool: True if restart successful, False otherwise
        """
        try:
            # Disconnect device
            subprocess.run(["adb", "disconnect", self.device_id], check=True)
            
            # Reconnect device
            result = subprocess.run(["adb", "connect", self.device_id], check=True, capture_output=True)
            
            if "connected" in result.stdout.decode():
                logger.info(f"Successfully restarted device {self.device_id}")
                # Reinitialize connection
                self.d = None
                return self.connect()
            else:
                logger.error(f"Failed to restart device {self.device_id}: {result.stdout.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error restarting device {self.device_id}: {e}")
            return False
