#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for base_phone_checker module.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_phone_checker import (
    BasePhoneChecker,
    PhoneCheckResult,
    PhoneCheckerError,
    DeviceConnectionError,
    UIInteractionError,
    normalize_phone_number
)
from tests.mocks import MockDevice, create_mock_device_with_config


class TestBasePhoneChecker(unittest.TestCase):
    """Test cases for BasePhoneChecker."""

    @patch('uiautomator2.connect')
    def test_init(self, mock_connect):
        """Test initialization of BasePhoneChecker."""
        # Setup mock
        mock_device = MockDevice("127.0.0.1:5555")
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test initialization
        checker = ConcreteChecker("127.0.0.1:5555")
        self.assertEqual(checker.device_id, "127.0.0.1:5555")
        self.assertEqual(checker.source_name, "ConcreteChecker")
        mock_connect.assert_called_once_with("127.0.0.1:5555")

    @patch('uiautomator2.connect')
    def test_init_connection_error(self, mock_connect):
        """Test initialization with connection error."""
        # Setup mock to raise exception
        mock_connect.side_effect = Exception("Connection failed")

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test initialization with error
        with self.assertRaises(DeviceConnectionError):
            ConcreteChecker("127.0.0.1:5555")

    @patch('uiautomator2.connect')
    def test_click_element(self, mock_connect):
        """Test click_element method."""
        # Setup mock
        config = {
            "elements": {
                "test_button": {"exists": True, "text": "Test Button"}
            }
        }
        mock_device = create_mock_device_with_config("127.0.0.1:5555", config)
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test click_element
        checker = ConcreteChecker("127.0.0.1:5555")
        result = checker.click_element({"text": "test_button"})
        self.assertTrue(result)
        mock_device(text="test_button").click.assert_called_once()

    @patch('uiautomator2.connect')
    def test_click_element_not_found(self, mock_connect):
        """Test click_element method when element not found."""
        # Setup mock
        config = {
            "elements": {
                "test_button": {"exists": False, "text": "Test Button"}
            }
        }
        mock_device = create_mock_device_with_config("127.0.0.1:5555", config)
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test click_element with non-existent element
        checker = ConcreteChecker("127.0.0.1:5555")
        with self.assertRaises(UIInteractionError):
            checker.click_element({"text": "test_button"})

    @patch('uiautomator2.connect')
    def test_input_text(self, mock_connect):
        """Test input_text method."""
        # Setup mock
        config = {
            "elements": {
                "input_field": {"exists": True, "text": ""}
            }
        }
        mock_device = create_mock_device_with_config("127.0.0.1:5555", config)
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test input_text
        checker = ConcreteChecker("127.0.0.1:5555")
        result = checker.input_text({"text": "input_field"}, "Test Input")
        self.assertTrue(result)
        
        element = mock_device(text="input_field")
        element.click.assert_called_once()
        element.clear_text.assert_called_once()
        element.set_text.assert_called_once_with("Test Input")

    @patch('uiautomator2.connect')
    def test_wait_for_element(self, mock_connect):
        """Test wait_for_element method."""
        # Setup mock
        config = {
            "elements": {
                "test_element": {"exists": True, "text": "Test Element"}
            }
        }
        mock_device = create_mock_device_with_config("127.0.0.1:5555", config)
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test wait_for_element
        checker = ConcreteChecker("127.0.0.1:5555")
        result = checker.wait_for_element({"text": "test_element"})
        self.assertTrue(result)

    @patch('uiautomator2.connect')
    def test_element_exists(self, mock_connect):
        """Test element_exists method."""
        # Setup mock
        config = {
            "elements": {
                "test_element": {"exists": True, "text": "Test Element"},
                "missing_element": {"exists": False, "text": "Missing Element"}
            }
        }
        mock_device = create_mock_device_with_config("127.0.0.1:5555", config)
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test element_exists
        checker = ConcreteChecker("127.0.0.1:5555")
        self.assertTrue(checker.element_exists({"text": "test_element"}))
        self.assertFalse(checker.element_exists({"text": "missing_element"}))

    @patch('uiautomator2.connect')
    def test_get_element_text(self, mock_connect):
        """Test get_element_text method."""
        # Setup mock
        config = {
            "elements": {
                "test_element": {"exists": True, "text": "Test Element Text"},
                "missing_element": {"exists": False, "text": "Missing Element"}
            }
        }
        mock_device = create_mock_device_with_config("127.0.0.1:5555", config)
        mock_connect.return_value = mock_device

        # Create a concrete subclass for testing
        class ConcreteChecker(BasePhoneChecker):
            def launch_app(self):
                return True

            def check_number(self, phone):
                return PhoneCheckResult(phone_number=phone, status="Test", source="Test")

        # Test get_element_text
        checker = ConcreteChecker("127.0.0.1:5555")
        self.assertEqual(checker.get_element_text({"text": "test_element"}), "Test Element Text")
        self.assertIsNone(checker.get_element_text({"text": "missing_element"}))

    def test_normalize_phone_number(self):
        """Test normalize_phone_number function."""
        self.assertEqual(normalize_phone_number("+79123456789"), "+79123456789")
        self.assertEqual(normalize_phone_number("79123456789"), "+79123456789")
        self.assertEqual(normalize_phone_number("9123456789"), "+79123456789")
        self.assertEqual(normalize_phone_number("+12025550108"), "+12025550108")


if __name__ == '__main__':
    unittest.main()
