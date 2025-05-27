#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kaspersky Who Calls phone number checker implementation.
Inherits from BasePhoneChecker and provides specific implementation for Kaspersky Who Calls app.
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
APP_PACKAGE = "com.kaspersky.who_calls"
APP_ACTIVITY = "com.kaspersky.who_calls.LauncherActivityAlias"

# UI element locators
LOC_BTN_CHECK_NUMBER = {'description': 'Check number'}
LOC_INPUT_FIELD = {'className': 'android.widget.EditText'}
LOC_BTN_DO_CHECK = {'text': 'Check'}
LOC_NO_FEEDBACK_TEXT = {'text': 'No feedback on the number'}
LOC_BTN_CANCEL = {'resourceId': 'android:id/button2'}
LOC_SPAM_TEXT = {'textContains': 'SPAM!'}
LOC_USEFUL_TEXT = {'textContains': 'useful'}

# Configure logger
logger = logging.getLogger("phone_checker.kaspersky")


class KasperskyWhoCallsChecker(BasePhoneChecker):
    """Checker implementation for Kaspersky Who Calls app."""

    def __init__(self, device: str):
        """
        Initialize the Kaspersky Who Calls checker.
        
        Args:
            device: Android device identifier (e.g., "127.0.0.1:5555")
        """
        super().__init__(device)
        self.app_package = APP_PACKAGE
        self.app_activity = APP_ACTIVITY
        self.source_name = "Kaspersky"

    def launch_app(self) -> bool:
        """
        Launch Kaspersky Who Calls app and navigate to check number screen.
        
        Returns:
            bool: True if app launched successfully, False otherwise
            
        Raises:
            AppLaunchError: If app fails to launch or navigate to check screen
        """
        logger.info("Launching Kaspersky Who Calls")
        try:
            self.d.app_start(self.app_package, activity=self.app_activity)
        except Exception as e:
            error_msg = f"Failed to launch Kaspersky Who Calls: {e}"
            logger.error(error_msg)
            raise AppLaunchError(error_msg) from e

        # Wait for and click "Check number" button
        try:
            if not self.click_element(LOC_BTN_CHECK_NUMBER, timeout=10):
                error_msg = "Check number button not found"
                logger.error(error_msg)
                raise AppLaunchError(error_msg)
        except UIInteractionError as e:
            raise AppLaunchError(f"Failed to click Check number button: {e}") from e

        # Wait for input field to appear
        if not self.wait_for_element(LOC_INPUT_FIELD, timeout=8):
            error_msg = "Input field did not appear after clicking Check number"
            logger.error(error_msg)
            raise AppLaunchError(error_msg)

        return True

    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number using Kaspersky Who Calls app.
        
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
            except UIInteractionError as e:
                raise UIInteractionError(f"Failed to input phone number: {e}")

            # Click Check button
            try:
                self.click_element(LOC_BTN_DO_CHECK, timeout=5)
            except UIInteractionError as e:
                raise UIInteractionError(f"Failed to click Check button: {e}")

            # Check for "No feedback" popup
            if self.element_exists(LOC_NO_FEEDBACK_TEXT, timeout=4):
                logger.info("Number not found - closing popup")
                try:
                    self.click_element(LOC_BTN_CANCEL, timeout=3)
                except UIInteractionError:
                    # If cancel button click fails, try pressing back
                    self.d.press("back")
                result.status = "Not in database"
            else:
                # Check for spam or safe status
                if self.element_exists(LOC_SPAM_TEXT, timeout=4):
                    result.status = "Spam"
                    spam_text = self.get_element_text(LOC_SPAM_TEXT)
                    if spam_text:
                        result.details = spam_text
                elif self.element_exists(LOC_USEFUL_TEXT, timeout=4):
                    result.status = "Safe"
                    useful_text = self.get_element_text(LOC_USEFUL_TEXT)
                    if useful_text:
                        result.details = useful_text
                else:
                    result.status = "Unknown"

            # Close information popup (if any) and return to input
            self.d.press("back")
            if not self.wait_for_element(LOC_INPUT_FIELD, timeout=5):
                # If input field doesn't appear, press back again
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
    Command-line interface for Kaspersky Who Calls checker.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Check phone numbers using Kaspersky Who Calls")
    parser.add_argument('-i', '--input', type=Path, required=True, help="File with phone numbers")
    parser.add_argument('-o', '--output', type=Path, default=Path('results_kaspersky.csv'), help="Output CSV file")
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
        checker = KasperskyWhoCallsChecker(args.device)
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
