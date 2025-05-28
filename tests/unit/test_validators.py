#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for validators.
"""

import unittest
from app.utils.validators import Validator, PhoneNumberModel, CheckRequestValidator
from app.utils.constants import CheckerSource
from pydantic import ValidationError


class TestValidators(unittest.TestCase):
    """Test cases for validators."""
    
    def test_validate_phone_number(self):
        """Test phone number validation."""
        # Valid phone numbers
        self.assertEqual(Validator.validate_phone_number("89123456789"), "+79123456789")
        self.assertEqual(Validator.validate_phone_number("+12025550108"), "+12025550108")
        
        # Invalid phone numbers
        with self.assertRaises(ValueError):
            Validator.validate_phone_number("123")  # Too short
        
        with self.assertRaises(ValueError):
            Validator.validate_phone_number("1" * 30)  # Too long
    
    def test_validate_phone_numbers(self):
        """Test phone numbers list validation."""
        # Valid phone numbers list
        valid_phones = ["89123456789", "+12025550108"]
        normalized = Validator.validate_phone_numbers(valid_phones)
        self.assertEqual(normalized, ["+79123456789", "+12025550108"])
        
        # Empty list
        with self.assertRaises(ValueError):
            Validator.validate_phone_numbers([])
        
        # Too many numbers
        with self.assertRaises(ValueError):
            Validator.validate_phone_numbers(["123456789"] * 101)
        
        # List with invalid numbers
        with self.assertRaises(ValueError):
            Validator.validate_phone_numbers(["89123456789", "123"])
    
    def test_validate_checker_source(self):
        """Test checker source validation."""
        # Valid sources
        self.assertEqual(Validator.validate_checker_source("kaspersky"), "kaspersky")
        self.assertEqual(Validator.validate_checker_source("truecaller"), "truecaller")
        self.assertEqual(Validator.validate_checker_source("getcontact"), "getcontact")
        self.assertIsNone(Validator.validate_checker_source(None))
        
        # Invalid source
        with self.assertRaises(ValueError):
            Validator.validate_checker_source("invalid_source")
    
    def test_phone_number_model(self):
        """Test PhoneNumberModel."""
        # Valid phone number
        model = PhoneNumberModel(number="+79123456789")
        self.assertEqual(model.number, "+79123456789")
        
        # Normalization
        model = PhoneNumberModel(number="89123456789")
        self.assertEqual(model.number, "+79123456789")
        
        # Invalid phone number
        with self.assertRaises(ValidationError):
            PhoneNumberModel(number="abc")
    
    def test_check_request_validator(self):
        """Test CheckRequestValidator."""
        # Valid request
        validator = CheckRequestValidator(
            numbers=["89123456789", "+12025550108"],
            use_cache=True,
            force_source="kaspersky"
        )
        self.assertEqual(validator.numbers, ["+79123456789", "+12025550108"])
        self.assertTrue(validator.use_cache)
        self.assertEqual(validator.force_source, "kaspersky")
        
        # Default values
        validator = CheckRequestValidator(numbers=["89123456789"])
        self.assertTrue(validator.use_cache)
        self.assertIsNone(validator.force_source)
        
        # Invalid numbers
        with self.assertRaises(ValidationError):
            CheckRequestValidator(numbers=[])
        
        # Invalid source
        with self.assertRaises(ValidationError):
            CheckRequestValidator(
                numbers=["89123456789"],
                force_source="invalid_source"
            )


if __name__ == "__main__":
    unittest.main()
