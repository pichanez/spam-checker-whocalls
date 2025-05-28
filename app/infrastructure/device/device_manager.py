#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Device manager for managing Android devices.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from app.infrastructure.device.device_interface import DeviceInterface
from app.infrastructure.device.android_device import AndroidDevice
from app.utils.exceptions import DeviceConnectionError

# Configure logging
logger = logging.getLogger("phone_checker.device_manager")


class DeviceManager:
    """Manager for Android devices."""
    
    def __init__(self, device_config: Dict[str, str], check_interval: int = 60):
        """
        Initialize the device manager.
        
        Args:
            device_config: Dictionary of device name to device ID
            check_interval: Interval for checking device health in seconds
        """
        self.device_config = device_config
        self.check_interval = check_interval
        self.devices: Dict[str, DeviceInterface] = {}
        self.device_status: Dict[str, Dict[str, Any]] = {}
        self.last_check: Dict[str, datetime] = {}
        
        # Initialize devices
        for name, device_id in device_config.items():
            self.devices[name] = AndroidDevice(device_id)
    
    def get_device(self, name: str) -> Optional[DeviceInterface]:
        """
        Get a device by name.
        
        Args:
            name: Device name
            
        Returns:
            Optional[DeviceInterface]: Device interface or None if not found
        """
        return self.devices.get(name)
    
    def get_all_devices(self) -> Dict[str, DeviceInterface]:
        """
        Get all devices.
        
        Returns:
            Dict[str, DeviceInterface]: Dictionary of device name to device interface
        """
        return self.devices
    
    async def check_device_health(self, name: str) -> Dict[str, Any]:
        """
        Check health of a device.
        
        Args:
            name: Device name
            
        Returns:
            Dict[str, Any]: Device status
        """
        device = self.get_device(name)
        if not device:
            return {
                "connected": False,
                "error": f"Device {name} not found"
            }
        
        try:
            status = device.get_device_status()
            self.device_status[name] = status
            self.last_check[name] = datetime.utcnow()
            return status
        except Exception as e:
            logger.error(f"Error checking device {name}: {e}")
            status = {
                "connected": False,
                "error": str(e)
            }
            self.device_status[name] = status
            self.last_check[name] = datetime.utcnow()
            return status
    
    async def check_all_devices(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all devices.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of device name to status
        """
        results = {}
        
        for name in self.devices.keys():
            results[name] = await self.check_device_health(name)
        
        return results
    
    async def start_monitoring(self) -> None:
        """Start monitoring devices."""
        logger.info("Starting device monitoring")
        while True:
            await self.check_all_devices()
            await asyncio.sleep(self.check_interval)
    
    async def restart_device(self, name: str) -> bool:
        """
        Restart a device.
        
        Args:
            name: Device name
            
        Returns:
            bool: True if restart successful, False otherwise
        """
        device = self.get_device(name)
        if not device:
            return False
        
        try:
            return device.restart()
        except Exception as e:
            logger.error(f"Error restarting device {name}: {e}")
            return False
    
    async def recover_device(self, name: str) -> bool:
        """
        Try to recover a device.
        
        Args:
            name: Device name
            
        Returns:
            bool: True if recovery successful, False otherwise
        """
        status = await self.check_device_health(name)
        
        if not status.get("connected", False):
            return await self.restart_device(name)
        
        device = self.get_device(name)
        if not device:
            return False
        
        try:
            # If device is connected but screen is off or locked
            if not status.get("screen_on", False) or not status.get("unlocked", False):
                # Try to wake up and unlock
                result = device.execute_shell("input keyevent KEYCODE_WAKEUP && input keyevent KEYCODE_MENU")
                logger.info(f"Attempted to wake up and unlock device {name}")
                return True
            
            return True
        except Exception as e:
            logger.error(f"Error recovering device {name}: {e}")
            return False
