#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for device interface and implementations.
"""

import unittest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from app.infrastructure.device.device_interface import DeviceInterface
from app.infrastructure.device.android_device import AndroidDevice
from app.utils.exceptions import DeviceConnectionError, UIInteractionError


class TestAndroidDevice(unittest.TestCase):
    """Test cases for AndroidDevice implementation."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock uiautomator2
        self.u2_patcher = patch('app.infrastructure.device.android_device.u2')
        self.mock_u2 = self.u2_patcher.start()
        
        # Mock device
        self.mock_device = MagicMock()
        self.mock_u2.connect.return_value = self.mock_device
        
        # Create AndroidDevice instance
        self.device = AndroidDevice("test_device_id")
    
    def tearDown(self):
        """Tear down test environment."""
        self.u2_patcher.stop()
    
    def test_connect_success(self):
        """Test successful device connection."""
        # Setup
        self.mock_device.screen_on.return_value = True
        self.mock_device.unlock.return_value = True
        
        # Execute
        result = self.device.connect()
        
        # Assert
        self.assertTrue(result)
        self.mock_u2.connect.assert_called_once_with("test_device_id")
        self.mock_device.screen_on.assert_called_once()
        self.mock_device.unlock.assert_called_once()
    
    def test_connect_failure(self):
        """Test failed device connection."""
        # Setup
        self.mock_u2.connect.side_effect = Exception("Connection failed")
        
        # Execute and Assert
        with self.assertRaises(DeviceConnectionError):
            self.device.connect()
    
    def test_launch_app_success(self):
        """Test successful app launch."""
        # Setup
        self.device.d = self.mock_device
        
        # Execute
        result = self.device.launch_app("com.test.app", "MainActivity")
        
        # Assert
        self.assertTrue(result)
        self.mock_device.app_start.assert_called_once_with("com.test.app", "MainActivity")
    
    def test_launch_app_no_activity(self):
        """Test app launch without activity."""
        # Setup
        self.device.d = self.mock_device
        
        # Execute
        result = self.device.launch_app("com.test.app")
        
        # Assert
        self.assertTrue(result)
        self.mock_device.app_start.assert_called_once_with("com.test.app")
    
    def test_launch_app_failure(self):
        """Test failed app launch."""
        # Setup
        self.device.d = self.mock_device
        self.mock_device.app_start.side_effect = Exception("Launch failed")
        
        # Execute
        result = self.device.launch_app("com.test.app")
        
        # Assert
        self.assertFalse(result)
    
    def test_close_app_success(self):
        """Test successful app close."""
        # Setup
        self.device.d = self.mock_device
        
        # Execute
        result = self.device.close_app("com.test.app")
        
        # Assert
        self.assertTrue(result)
        self.mock_device.app_stop.assert_called_once_with("com.test.app")
    
    def test_close_app_failure(self):
        """Test failed app close."""
        # Setup
        self.device.d = self.mock_device
        self.mock_device.app_stop.side_effect = Exception("Close failed")
        
        # Execute
        result = self.device.close_app("com.test.app")
        
        # Assert
        self.assertFalse(result)
    
    def test_click_element_success(self):
        """Test successful element click."""
        # Setup
        self.device.d = self.mock_device
        mock_element = MagicMock()
        mock_element.exists.return_value = True
        self.mock_device.__call__.return_value = mock_element
        
        # Execute
        result = self.device.click_element({"text": "Test"})
        
        # Assert
        self.assertTrue(result)
        self.mock_device.__call__.assert_called_once_with(text="Test")
        mock_element.exists.assert_called_once_with(timeout=5)
        mock_element.click.assert_called_once()
    
    def test_click_element_not_found(self):
        """Test click on non-existent element."""
        # Setup
        self.device.d = self.mock_device
        mock_element = MagicMock()
        mock_element.exists.return_value = False
        self.mock_device.__call__.return_value = mock_element
        
        # Execute and Assert
        with self.assertRaises(UIInteractionError):
            self.device.click_element({"text": "Test"})
    
    def test_input_text_success(self):
        """Test successful text input."""
        # Setup
        self.device.d = self.mock_device
        mock_element = MagicMock()
        mock_element.exists.return_value = True
        self.mock_device.__call__.return_value = mock_element
        
        # Execute
        result = self.device.input_text({"text": "Input"}, "Test text")
        
        # Assert
        self.assertTrue(result)
        self.mock_device.__call__.assert_called_once_with(text="Input")
        mock_element.exists.assert_called_once_with(timeout=5)
        mock_element.click.assert_called_once()
        mock_element.clear_text.assert_called_once()
        mock_element.set_text.assert_called_once_with("Test text")
    
    def test_get_device_status_connected(self):
        """Test getting device status when connected."""
        # Setup
        self.device.d = self.mock_device
        self.mock_device.info = {
            "screenOn": True,
            "screenLocked": False
        }
        self.mock_device.shell.return_value.output = "level: 80"
        
        # Execute
        result = self.device.get_device_status()
        
        # Assert
        self.assertTrue(result["connected"])
        self.assertTrue(result["screen_on"])
        self.assertTrue(result["unlocked"])
        self.assertEqual(result["battery"], "80%")
    
    def test_get_device_status_not_connected(self):
        """Test getting device status when not connected."""
        # Setup
        self.device.d = None
        self.mock_u2.connect.side_effect = Exception("Connection failed")
        
        # Execute
        result = self.device.get_device_status()
        
        # Assert
        self.assertFalse(result["connected"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
