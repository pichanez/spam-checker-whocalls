#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for phone utilities.
"""

import unittest
from app.utils.phone_utils import normalize_phone_number, is_russian_number


class TestPhoneUtils(unittest.TestCase):
    """Test cases for phone utilities."""
    
    def test_normalize_phone_number(self):
        """Test phone number normalization."""
        # Test Russian numbers
        self.assertEqual(normalize_phone_number("89123456789"), "+79123456789")
        self.assertEqual(normalize_phone_number("79123456789"), "+79123456789")
        self.assertEqual(normalize_phone_number("9123456789"), "+79123456789")
        
        # Test international numbers
        self.assertEqual(normalize_phone_number("+12025550108"), "+12025550108")
        self.assertEqual(normalize_phone_number("12025550108"), "+12025550108")
        
        # Test with special characters
        self.assertEqual(normalize_phone_number("+1 (202) 555-0108"), "+12025550108")
        self.assertEqual(normalize_phone_number("+7-912-345-67-89"), "+79123456789")
        
        # Test empty and invalid inputs
        self.assertEqual(normalize_phone_number(""), "+")
        self.assertEqual(normalize_phone_number("abc"), "+")
    
    def test_is_russian_number(self):
        """Test Russian number detection."""
        # Test Russian numbers
        self.assertTrue(is_russian_number("+79123456789"))
        self.assertTrue(is_russian_number("89123456789"))
        self.assertTrue(is_russian_number("79123456789"))
        
        # Test non-Russian numbers
        self.assertFalse(is_russian_number("+12025550108"))
        self.assertFalse(is_russian_number("+442071234567"))
        
        # Test invalid inputs
        self.assertFalse(is_russian_number(""))
        self.assertFalse(is_russian_number("abc"))


if __name__ == "__main__":
    unittest.main()
