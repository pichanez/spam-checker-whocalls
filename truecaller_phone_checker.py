#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Truecaller phone number checker implementation.
Inherits from BasePhoneChecker and provides specific implementation for Truecaller app.
"""

import argparse
import csv
import logging
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Any

from base_phone_checker import (
    BasePhoneChecker,
    PhoneCheckResult,
    UIInteractionError,
    DeviceConnectionError,
    AppLaunchError,
)

# App package and activity
APP_PACKAGE = "com.truecaller"
APP_ACTIVITY = "com.truecaller.ui.TruecallerInit"

# UI element locators
LOC_SEARCH_LABEL = {'resourceId': 'com.truecaller:id/searchBarLabel'}   # "Search numbers…" bar
LOC_INPUT_FIELD = {'resourceId': 'com.truecaller:id/search_field'}     # AutoCompleteTextView for input
LOC_SEARCH_WEB = {'resourceId': 'com.truecaller:id/searchWeb'}        # "SEARCH THE WEB" button when no data
LOC_SPAM_TEXT = {'textContains': 'SPAM'}                            # Spam label in result
LOC_NAME_OR_NUMBER = {'resourceId': 'com.truecaller:id/nameOrNumber'}     # Name or number in header
LOC_NUMBER_DETAILS = {'resourceId': 'com.truecaller:id/numberDetails'}    # Number details (carrier, region)
LOC_PHONE_NUMBER = {'resourceId': 'com.truecaller:id/phoneNumber'}      # Number text on result screen

# Configure logger
logger = logging.getLogger("phone_checker.truecaller")


class TruecallerChecker(BasePhoneChecker):
    """Checker implementation for Truecaller app."""

    def __init__(self, device: str):
        """
        Initialize the Truecaller checker.
        
        Args:
            device: Android device identifier (e.g., "127.0.0.1:5555")
        """
        super().__init__(device)
        self.app_package = APP_PACKAGE
        self.app_activity = APP_ACTIVITY
        self.source_name = "Truecaller"

    def launch_app(self) -> bool:
        """
        Launch Truecaller app and navigate to search screen.
        
        Returns:
            bool: True if app launched successfully, False otherwise
            
        Raises:
            AppLaunchError: If app fails to launch or navigate to search screen
        """
        logger.info("Launching Truecaller")
        try:
            self.d.app_start(self.app_package, activity=self.app_activity)
        except Exception as e:
            error_msg = f"Failed to launch Truecaller: {e}"
            logger.error(error_msg)
            raise AppLaunchError(error_msg) from e

        # Handle permission dialogs if they appear
        for btn_text in ("ALLOW", "Allow", "Разрешить", "ALLOW ALL THE TIME"):
            if self.element_exists({'text': btn_text}, timeout=2):
                logger.info(f"Clicking system dialog: {btn_text}")
                try:
                    self.click_element({'text': btn_text})
                except UIInteractionError:
                    logger.warning(f"Failed to click {btn_text} button, continuing anyway")

        # Click on search label to open search field
        try:
            if not self.click_element(LOC_SEARCH_LABEL, timeout=5):
                error_msg = "Search label not found"
                logger.error(error_msg)
                raise AppLaunchError(error_msg)
        except UIInteractionError as e:
            raise AppLaunchError(f"Failed to click search label: {e}") from e

        # Wait for input field to appear
        if not self.wait_for_element(LOC_INPUT_FIELD, timeout=5):
            error_msg = "Input field did not appear after clicking search"
            logger.error(error_msg)
            raise AppLaunchError(error_msg)

        return True

    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number using Truecaller app.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        logger.info(f"Checking number: {phone}")
        result = PhoneCheckResult(
            phone_number=phone,
            status="Unknown",
            source=self.source_name
        )

        try:
            # Input phone number
            try:
                self.input_text(LOC_INPUT_FIELD, phone, timeout=5)
                self.d.press("enter")
            except UIInteractionError as e:
                raise UIInteractionError(f"Failed to input phone number: {e}")

            # Wait for results to load
            if not (self.wait_for_element(LOC_PHONE_NUMBER, timeout=5) or 
                    self.element_exists(LOC_SPAM_TEXT, timeout=5)):
                raise UIInteractionError("Result screen did not load")

            # Check if "Search the web" button exists (no entry in database)
            if self.element_exists(LOC_SEARCH_WEB, timeout=2):
                logger.info("No entry in database - SEARCH THE WEB found")
                result.status = "Not in database"
            else:
                # Check if spam
                if self.element_exists(LOC_SPAM_TEXT, timeout=3):
                    result.status = "Spam"
                    spam_text = self.get_element_text(LOC_SPAM_TEXT)
                    if spam_text:
                        result.details = spam_text
                else:
                    # Safe number - extract name/number and details
                    name_or_num = self.get_element_text(LOC_NAME_OR_NUMBER)
                    details = ""
                    if self.element_exists(LOC_NUMBER_DETAILS, timeout=2):
                        details = self.get_element_text(LOC_NUMBER_DETAILS)
                    
                    result.status = "Safe"
                    result.details = f"{name_or_num}; {details}" if details and name_or_num else \
                                    name_or_num or details or ""

            # Return to input screen
            self.d.press("back")
            if not self.wait_for_element(LOC_INPUT_FIELD, timeout=3):
                self.d.press("back")
                self.wait_for_element(LOC_INPUT_FIELD, timeout=5)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} → {result.status}")
        return result


def write_results(path: Path, results: List[PhoneCheckResult]) -> None:
    """
    Save results to a CSV file.
    
    Args:
        path: Path to save the results
        results: List of check results
    """
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['phone_number', 'status', 'details', 'source'])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def main() -> int:
    """
    Command-line interface for Truecaller checker.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Check phone numbers using Truecaller")
    parser.add_argument('-i', '--input', type=Path, required=True, help="File with phone numbers")
    parser.add_argument('-o', '--output', type=Path, default=Path('results_truecaller.csv'), help="Output CSV file")
    parser.add_argument('-d', '--device', type=str, default='127.0.0.1:5555', help="Android device ID")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    # Read phone numbers from file
    from base_phone_checker import read_phone_list
    phones = read_phone_list(str(args.input))
    logger.info(f"Loaded {len(phones)} numbers from {args.input}")

    # Create checker and check numbers
    try:
        checker = TruecallerChecker(args.device)
        checker.launch_app()
        results = [checker.check_number(num) for num in phones]
        checker.close_app()
        write_results(args.output, results)
        logger.info(f"Results saved to {args.output}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
