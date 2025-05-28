#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Input validation utilities for the phone-spam-checker application.
"""

import re
from typing import List, Dict, Any, Optional, Union, Type, TypeVar, Generic, cast
from pydantic import BaseModel, validator, ValidationError, constr

from app.utils.constants import CheckerSource, PhoneStatus
from app.utils.phone_utils import normalize_phone_number

T = TypeVar('T')


class Validator(Generic[T]):
    """Generic validator for input data."""
    
    @staticmethod
    def validate_phone_number(phone: str) -> str:
        """
        Validate and normalize a phone number.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            str: Normalized phone number
            
        Raises:
            ValueError: If phone number is invalid
        """
        # Basic validation
        if not phone or len(phone) < 10:
            raise ValueError("Phone number is too short")
        
        if len(phone) > 20:
            raise ValueError("Phone number is too long")
        
        # Normalize
        normalized = normalize_phone_number(phone)
        
        # Check format
        if not re.match(r'^\+[0-9]{10,15}$', normalized):
            raise ValueError(f"Invalid phone number format: {normalized}")
        
        return normalized
    
    @staticmethod
    def validate_phone_numbers(phones: List[str]) -> List[str]:
        """
        Validate and normalize a list of phone numbers.
        
        Args:
            phones: List of phone numbers to validate
            
        Returns:
            List[str]: List of normalized phone numbers
            
        Raises:
            ValueError: If any phone number is invalid
        """
        if not phones:
            raise ValueError("Phone number list cannot be empty")
        
        if len(phones) > 100:
            raise ValueError("Too many phone numbers (max 100)")
        
        result = []
        errors = []
        
        for i, phone in enumerate(phones):
            try:
                normalized = Validator.validate_phone_number(phone)
                result.append(normalized)
            except ValueError as e:
                errors.append(f"Phone {i+1} ({phone}): {str(e)}")
        
        if errors:
            raise ValueError(f"Invalid phone numbers: {'; '.join(errors)}")
        
        return result
    
    @staticmethod
    def validate_checker_source(source: Optional[str]) -> Optional[str]:
        """
        Validate checker source.
        
        Args:
            source: Checker source to validate
            
        Returns:
            Optional[str]: Validated source or None
            
        Raises:
            ValueError: If source is invalid
        """
        if source is None:
            return None
        
        if source not in CheckerSource.all_sources():
            raise ValueError(f"Invalid source: {source}. Must be one of: {', '.join(CheckerSource.all_sources())}")
        
        return source
    
    @staticmethod
    def validate_model(data: Dict[str, Any], model_class: Type[T]) -> T:
        """
        Validate data against a Pydantic model.
        
        Args:
            data: Data to validate
            model_class: Pydantic model class
            
        Returns:
            T: Validated model instance
            
        Raises:
            ValueError: If validation fails
        """
        try:
            return model_class(**data)
        except ValidationError as e:
            raise ValueError(f"Validation error: {e}")


class PhoneNumberModel(BaseModel):
    """Model for phone number validation."""
    number: constr(regex=r'^\+?[0-9]{10,15}$')
    
    @validator('number')
    def normalize_phone(cls, v):
        """Normalize phone number."""
        return normalize_phone_number(v)


class CheckRequestValidator(BaseModel):
    """Validator for check request."""
    numbers: List[str]
    use_cache: bool = True
    force_source: Optional[str] = None
    
    @validator('numbers')
    def validate_numbers(cls, v):
        """Validate phone numbers."""
        return Validator.validate_phone_numbers(v)
    
    @validator('force_source')
    def validate_source(cls, v):
        """Validate source."""
        return Validator.validate_checker_source(v)
