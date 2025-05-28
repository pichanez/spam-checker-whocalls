#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phone checker strategy interface and implementations.
Provides a common interface for all phone checker strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type

from app.api.models import PhoneCheckResult
from app.utils.constants import PhoneStatus, CheckerSource
from app.utils.exceptions import PhoneCheckerError
from app.utils.phone_utils import is_russian_number
from app.infrastructure.device.device_interface import DeviceInterface


class PhoneCheckerStrategy(ABC):
    """Abstract strategy for phone number checking."""
    
    def __init__(self, device: DeviceInterface):
        """
        Initialize the checker strategy.
        
        Args:
            device: Device interface implementation
        """
        self.device = device
        self.app_package = ""  # To be set by subclasses
        self.app_activity = ""  # To be set by subclasses
        self.source_name = self.__class__.__name__
    
    @abstractmethod
    def can_handle(self, phone_number: str) -> bool:
        """
        Check if this strategy can handle the given phone number.
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            bool: True if this strategy can handle the phone number, False otherwise
        """
        pass
    
    @abstractmethod
    def launch_app(self) -> bool:
        """
        Launch the application and prepare it for number checking.
        
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number and return the result.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        pass
    
    def close_app(self) -> None:
        """Close the application."""
        if self.app_package:
            self.device.close_app(self.app_package)


class KasperskyPhoneCheckerStrategy(PhoneCheckerStrategy):
    """Strategy for checking phone numbers using Kaspersky Who Calls."""
    
    def __init__(self, device: DeviceInterface):
        """Initialize the Kaspersky checker strategy."""
        super().__init__(device)
        self.app_package = "com.kaspersky.who_calls"
        self.app_activity = "com.kaspersky.who_calls.LauncherActivityAlias"
        self.source_name = CheckerSource.KASPERSKY
    
    def can_handle(self, phone_number: str) -> bool:
        """
        Check if this strategy can handle the given phone number.
        Kaspersky works best with Russian phone numbers.
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            bool: True if this strategy can handle the phone number, False otherwise
        """
        return is_russian_number(phone_number)
    
    def launch_app(self) -> bool:
        """
        Launch the Kaspersky Who Calls application.
        
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        return self.device.launch_app(self.app_package, self.app_activity)
    
    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number using Kaspersky Who Calls.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        try:
            # Launch app if not already launched
            if not self.launch_app():
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to launch Kaspersky Who Calls",
                    source=self.source_name
                )
            
            # Click on "Check number" button
            check_number_button = {'description': 'Check number'}
            if not self.device.click_element(check_number_button):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to find 'Check number' button",
                    source=self.source_name
                )
            
            # Input phone number
            input_field = {"className": "android.widget.EditText"}
            if not self.device.input_text(input_field, phone):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to input phone number",
                    source=self.source_name
                )
            
            # Click on "Check" button
            check_button = {"text": "Check"}
            if not self.device.click_element(check_button):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to find 'Check' button",
                    source=self.source_name
                )
            
            # Wait for results
            # Check for "No feedback" message
            no_feedback = {'text': 'No feedback on the number'}
            if self.device.element_exists(no_feedback, timeout=5):
                self.device.click_element({'resourceId': 'android:id/button2'})
                self.device.press("back")

                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.NOT_IN_DB,
                    details="Number not found in database",
                    source=self.source_name
                )
            
            # Check for SPAM indicator
            spam_indicator = {'textContains': 'SPAM!'}
            if self.device.element_exists(spam_indicator, timeout=1):
                self.device.press("back")
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.SPAM,
                    details="Marked as spam",
                    source=self.source_name
                )
            
            # Check for useful number
            useful_indicator = {'textContains': 'useful'}
            if self.device.element_exists(useful_indicator, timeout=1):
                self.device.press("back")
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.SAFE,
                    details="Might be useful",
                    source=self.source_name
                )
            
            self.device.press("back")

            # Default case if no specific indicators found
            return PhoneCheckResult(
                phone_number=phone,
                status=PhoneStatus.UNKNOWN,
                details="Could not determine status",
                source=self.source_name
            )
            
        except Exception as e:
            return PhoneCheckResult(
                phone_number=phone,
                status=PhoneStatus.ERROR,
                details=f"Error checking number: {str(e)}",
                source=self.source_name
            )


class TruecallerPhoneCheckerStrategy(PhoneCheckerStrategy):
    """Strategy for checking phone numbers using Truecaller."""
    
    def __init__(self, device: DeviceInterface):
        """Initialize the Truecaller checker strategy."""
        super().__init__(device)
        self.app_package = "com.truecaller"
        self.app_activity = "com.truecaller.ui.TruecallerInit"
        self.source_name = CheckerSource.TRUECALLER
    
    def can_handle(self, phone_number: str) -> bool:
        """
        Check if this strategy can handle the given phone number.
        Truecaller works with international numbers.
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            bool: True if this strategy can handle the phone number, False otherwise
        """
        # Truecaller can handle any number, but we prioritize non-Russian numbers
        return not is_russian_number(phone_number)
    
    def launch_app(self) -> bool:
        """
        Launch the Truecaller application.
        
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        return self.device.launch_app(self.app_package, self.app_activity)
    
    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number using Truecaller.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        try:
            # Launch app if not already launched
            if not self.launch_app():
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to launch Truecaller",
                    source=self.source_name
                )
            
            # Click on search bar
            search_bar = {'resourceId': 'com.truecaller:id/searchBarLabel'}
            if not self.device.click_element(search_bar):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to find search bar",
                    source=self.source_name
                )
            
            # Input phone number
            search_field = {'resourceId': 'com.truecaller:id/search_field'} 
            if not self.device.input_text(search_field, phone, timeout=5):
                
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to input phone number",
                    source=self.source_name
                )
            
            self.device.press("enter")

            # Check for "Search web" message (indicating number not found)
            search_web = {'resourceId': 'com.truecaller:id/searchWeb'}
            if self.device.element_exists(search_web, timeout=5):
                self.device.press("back")
                self.device.press("back")
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.NOT_IN_DB,
                    details="Number not found in database",
                    source=self.source_name
                )
            
            # Check for SPAM indicator
            spam_indicator = {'textContains': 'SPAM'}
            if self.device.element_exists(spam_indicator, timeout=1):
                # Get name/number
                name_element = {"resourceId": "com.truecaller:id/nameOrNumber"}
                name = self.device.get_element_text(name_element) or "Unknown"
                
                # Get details
                details_element = {"resourceId": "com.truecaller:id/numberDetails"}
                details = self.device.get_element_text(details_element) or ""
                self.device.press("back")
                self.device.press("back")
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.SPAM,
                    details=f"{name} - {details}",
                    source=self.source_name
                )
            
            # Check for regular number (not spam)
            name_element = {"resourceId": "com.truecaller:id/nameOrNumber"}
            name = self.device.get_element_text(name_element)
            
            if name:
                # Get details
                details_element = {"resourceId": "com.truecaller:id/numberDetails"}
                details = self.device.get_element_text(details_element) or ""
                self.device.press("back")
                self.device.press("back")
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.SAFE,
                    details=f"{name} - {details}",
                    source=self.source_name
                )
            
            # Default case if no specific indicators found
            return PhoneCheckResult(
                phone_number=phone,
                status=PhoneStatus.UNKNOWN,
                details="Could not determine status",
                source=self.source_name
            )
            
        except Exception as e:
            return PhoneCheckResult(
                phone_number=phone,
                status=PhoneStatus.ERROR,
                details=f"Error checking number: {str(e)}",
                source=self.source_name
            )


class GetContactPhoneCheckerStrategy(PhoneCheckerStrategy):
    """Strategy for checking phone numbers using GetContact."""
    
    def __init__(self, device: DeviceInterface):
        """Initialize the GetContact checker strategy."""
        super().__init__(device)
        self.app_package = "app.source.getcontact"
        self.app_activity = ".MainActivity"
        self.source_name = CheckerSource.GETCONTACT
    
    def can_handle(self, phone_number: str) -> bool:
        """
        Check if this strategy can handle the given phone number.
        GetContact can handle any number as a fallback.
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            bool: True if this strategy can handle the phone number, False otherwise
        """
        # GetContact is used as a fallback, so it can handle any number
        # but with lower priority than specialized checkers
        return True
    
    def launch_app(self) -> bool:
        """
        Launch the GetContact application.
        
        Returns:
            bool: True if app launched successfully, False otherwise
        """
        return self.device.launch_app(self.app_package, self.app_activity)
    
    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number using GetContact.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        try:
            # Launch app if not already launched
            if not self.launch_app():
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to launch GetContact",
                    source=self.source_name
                )
            
            # Click on search button
            search_button = {"resourceId": "app.source.getcontact:id/search_button"}
            if not self.device.click_element(search_button):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to find search button",
                    source=self.source_name
                )
            
            # Input phone number
            search_field = {"resourceId": "app.source.getcontact:id/phone_number_edit_text"}
            if not self.device.input_text(search_field, phone):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to input phone number",
                    source=self.source_name
                )
            
            # Click on search button
            search_action = {"resourceId": "app.source.getcontact:id/search_action"}
            if not self.device.click_element(search_action):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.ERROR,
                    details="Failed to find search action button",
                    source=self.source_name
                )
            
            # Check for "No result" message
            no_result = {"text": "No result"}
            if self.device.element_exists(no_result, timeout=5):
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.NOT_IN_DB,
                    details="Number not found in database",
                    source=self.source_name
                )
            
            # Check for spam tag
            spam_tag = {"text": "Spam"}
            if self.device.element_exists(spam_tag, timeout=1):
                # Get name
                name_element = {"resourceId": "app.source.getcontact:id/name_text"}
                name = self.device.get_element_text(name_element) or "Unknown"
                
                # Get tags
                tags_element = {"resourceId": "app.source.getcontact:id/tags_text"}
                tags = self.device.get_element_text(tags_element) or ""
                
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.SPAM,
                    details=f"{name} - {tags}",
                    source=self.source_name
                )
            
            # Check for regular number (not spam)
            name_element = {"resourceId": "app.source.getcontact:id/name_text"}
            name = self.device.get_element_text(name_element)
            
            if name:
                # Get tags
                tags_element = {"resourceId": "app.source.getcontact:id/tags_text"}
                tags = self.device.get_element_text(tags_element) or ""
                
                return PhoneCheckResult(
                    phone_number=phone,
                    status=PhoneStatus.SAFE,
                    details=f"{name} - {tags}",
                    source=self.source_name
                )
            
            # Default case if no specific indicators found
            return PhoneCheckResult(
                phone_number=phone,
                status=PhoneStatus.UNKNOWN,
                details="Could not determine status",
                source=self.source_name
            )
            
        except Exception as e:
            return PhoneCheckResult(
                phone_number=phone,
                status=PhoneStatus.ERROR,
                details=f"Error checking number: {str(e)}",
                source=self.source_name
            )


class PhoneCheckerStrategyFactory:
    """Factory for creating phone checker strategies."""
    
    @staticmethod
    def create_strategy(strategy_type: str, device: DeviceInterface) -> PhoneCheckerStrategy:
        """
        Create a phone checker strategy.
        
        Args:
            strategy_type: Type of strategy to create
            device: Device interface implementation
            
        Returns:
            PhoneCheckerStrategy: Phone checker strategy
            
        Raises:
            ValueError: If strategy_type is invalid
        """
        if strategy_type == CheckerSource.KASPERSKY:
            return KasperskyPhoneCheckerStrategy(device)
        elif strategy_type == CheckerSource.TRUECALLER:
            return TruecallerPhoneCheckerStrategy(device)
        elif strategy_type == CheckerSource.GETCONTACT:
            return GetContactPhoneCheckerStrategy(device)
        else:
            raise ValueError(f"Invalid strategy type: {strategy_type}")
    
    @staticmethod
    def create_all_strategies(devices: Dict[str, DeviceInterface]) -> Dict[str, PhoneCheckerStrategy]:
        """
        Create all available phone checker strategies.
        
        Args:
            devices: Dictionary of device name to device interface
            
        Returns:
            Dict[str, PhoneCheckerStrategy]: Dictionary of strategy name to strategy
        """
        strategies = {}
        
        if CheckerSource.KASPERSKY in devices:
            strategies[CheckerSource.KASPERSKY] = KasperskyPhoneCheckerStrategy(devices[CheckerSource.KASPERSKY])
        
        if CheckerSource.TRUECALLER in devices:
            strategies[CheckerSource.TRUECALLER] = TruecallerPhoneCheckerStrategy(devices[CheckerSource.TRUECALLER])
        
        if CheckerSource.GETCONTACT in devices:
            strategies[CheckerSource.GETCONTACT] = GetContactPhoneCheckerStrategy(devices[CheckerSource.GETCONTACT])
        
        return strategies
    
    @staticmethod
    def get_strategy_for_number(phone: str, strategies: Dict[str, PhoneCheckerStrategy]) -> Optional[PhoneCheckerStrategy]:
        """
        Get appropriate strategy for a phone number.
        
        Args:
            phone: Phone number to check
            strategies: Available strategies
            
        Returns:
            Optional[PhoneCheckerStrategy]: Appropriate strategy or None if no suitable strategy found
        """
        # First try specialized strategies
        for strategy in strategies.values():
            if strategy.can_handle(phone):
                return strategy
        
        # If no specialized strategy found, return None
        return None
