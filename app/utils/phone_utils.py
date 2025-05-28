#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phone number utility functions.
"""

import re
from typing import List


def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number format.
    
    Converts various phone number formats to a standardized format with
    international prefix. Handles Russian numbers specially.
    
    Args:
        phone: Phone number in any format
        
    Returns:
        str: Normalized phone number with international prefix
        
    Examples:
        >>> normalize_phone_number("89123456789")
        "+79123456789"
        >>> normalize_phone_number("9123456789")
        "+79123456789"
        >>> normalize_phone_number("+12025550108")
        "+12025550108"
    """
    # Remove all non-digit characters except the plus sign
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + prefix if missing
    if not cleaned.startswith('+'):
        # Russian number format conversion
        if cleaned.startswith('8') and len(cleaned) == 11:
            return f"+7{cleaned[1:]}"
        elif cleaned.startswith('7') and len(cleaned) == 11:
            return f"+{cleaned}"
        elif len(cleaned) == 10 and not cleaned.startswith('7'):
            # Assume Russian number without prefix
            return f"+7{cleaned}"
        else:
            # For other countries, just add + prefix
            return f"+{cleaned}"
    
    return cleaned


def read_phone_list(path: str) -> List[str]:
    """
    Read phone numbers from a file.
    
    Args:
        path: Path to the file with phone numbers
        
    Returns:
        List[str]: List of normalized phone numbers
    """
    with open(path, 'r', encoding='utf-8') as f:
        return [normalize_phone_number(line.strip()) for line in f if line.strip()]


def is_russian_number(phone: str) -> bool:
    """
    Check if a phone number is Russian.
    
    Args:
        phone: Normalized phone number
        
    Returns:
        bool: True if the number is Russian, False otherwise
    """
    return bool(re.match(r"^\+79", normalize_phone_number(phone)))
