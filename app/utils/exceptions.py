#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exceptions for the phone-spam-checker application.
"""

class PhoneCheckerError(Exception):
    """Base exception for all phone checker errors."""
    pass


class DeviceConnectionError(PhoneCheckerError):
    """Error when connecting to Android device."""
    pass


class AppLaunchError(PhoneCheckerError):
    """Error when launching the application."""
    pass


class UIInteractionError(PhoneCheckerError):
    """Error when interacting with UI elements."""
    pass


class CacheError(PhoneCheckerError):
    """Error when interacting with cache."""
    pass


class ConfigurationError(PhoneCheckerError):
    """Error in configuration."""
    pass


class AuthenticationError(PhoneCheckerError):
    """Error in authentication."""
    pass


class RateLimitError(PhoneCheckerError):
    """Error when rate limit is exceeded."""
    pass
