#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constants for the phone-spam-checker application.
"""

class PhoneStatus:
    """Constants for phone number status."""
    SAFE = "Safe"
    SPAM = "Spam"
    NOT_IN_DB = "Not in database"
    ERROR = "Error"
    UNKNOWN = "Unknown"


class JobStatus:
    """Constants for job status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CheckerSource:
    """Constants for checker sources."""
    KASPERSKY = "kaspersky"
    TRUECALLER = "truecaller"
    GETCONTACT = "getcontact"
    
    @classmethod
    def all_sources(cls) -> list:
        """Get all available sources."""
        return [cls.KASPERSKY, cls.TRUECALLER, cls.GETCONTACT]


class CacheKeys:
    """Constants for cache keys."""
    PHONE_CHECK_PREFIX = "phone_check:"
    
    @staticmethod
    def phone_check_key(phone: str, source: str) -> str:
        """Generate cache key for phone check result."""
        return f"{CacheKeys.PHONE_CHECK_PREFIX}{source}:{phone}"
