#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GetContact phone number checker implementation.
Inherits from BasePhoneChecker and provides specific implementation for GetContact app.
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
APP_PACKAGE = "app.source.getcontact"
APP_ACTIVITY = ".ui.starter.StarterActivity"

# UI element locators
LOC_SEARCH_HINT = {'resourceId': 'view.newsfeed.search.unfocus.searchhint'}    # "Search by number"
LOC_INPUT_FIELD = {'resourceId': 'view.newsfeed.search.focus.searchfield'}     # EditText
LOC_NOT_FOUND = {'resourceId': 'view.numberdetail.profile.notFoundDisplayNameText'}
LOC_NAME_TEXT = {'resourceId': 'view.numberdetail.profile.displayNameText'}
LOC_SPAM_TEXT = {'textContains': 'Spam'}
LOC_LIMIT_DIALOG_CANCEL = {
    'resourceId': 'ConfirmationDialogNegativeButton',
    'text': 'CANCEL'
}
LOC_PRIVATE_MODE = {
    'resourceId': 'dialog.privateModeSettings.title'
}  # "Private Mode Settings" title

# Configure logger
logger = logging.getLogger("phone_checker.getcontact")


class GetContactChecker(BasePhoneChecker):
    """Checker implementation for GetContact app."""

    def __init__(self, device: str):
        """
        Initialize the GetContact checker.
        
        Args:
            device: Android device identifier (e.g., "127.0.0.1:5555")
        """
        super().__init__(device)
        self.app_package = APP_PACKAGE
        self.app_activity = APP_ACTIVITY
        self.source_name = "GetContact"

    def launch_app(self) -> bool:
        """
        Launch GetContact app and navigate to search screen.
        
        Returns:
            bool: True if app launched successfully, False otherwise
            
        Raises:
            AppLaunchError: If app fails to launch or navigate to search screen
        """
        logger.info("Launching GetContact")
        try:
            self.d.app_start(self.app_package, activity=self.app_activity)
        except Exception as e:
            error_msg = f"Failed to launch GetContact: {e}"
            logger.error(error_msg)
            raise AppLaunchError(error_msg) from e

        # Wait for search hint to appear
        if not self.wait_for_element(LOC_SEARCH_HINT, timeout=8):
            error_msg = "Search hint did not appear"
            logger.error(error_msg)
            raise AppLaunchError(error_msg)

        # Click on search hint to open search field
        try:
            self.click_element(LOC_SEARCH_HINT)
        except UIInteractionError as e:
            raise AppLaunchError(f"Failed to click search hint: {e}") from e

        # Wait for input field to appear
        if not self.wait_for_element(LOC_INPUT_FIELD, timeout=3):
            error_msg = "Input field did not appear after clicking search hint"
            logger.error(error_msg)
            raise AppLaunchError(error_msg)

        return True

    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Check a phone number using GetContact app.
        
        Args:
            phone: Phone number to check
            
        Returns:
            PhoneCheckResult: Result of the check
        """
        # Ensure phone number has + prefix
        if not phone.startswith("+"):
            phone = f"+{phone}"

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

            # Handle popup dialogs if they appear
            if self.element_exists(LOC_LIMIT_DIALOG_CANCEL, timeout=2):
                logger.info("Limit dialog detected → pressing CANCEL")
                try:
                    self.click_element(LOC_LIMIT_DIALOG_CANCEL)
                except UIInteractionError:
                    logger.warning("Failed to click CANCEL button, continuing anyway")

            if self.element_exists(LOC_PRIVATE_MODE, timeout=1):
                logger.info("Private-mode dialog detected → pressing BACK")
                self.d.press("back")

            # Wait for any valid result to appear
            cond_found = (
                self.wait_for_element(LOC_NOT_FOUND, timeout=8) or
                self.element_exists(LOC_NAME_TEXT) or
                self.element_exists(LOC_SPAM_TEXT)
            )
            if not cond_found:
                raise UIInteractionError("Result screen did not load")

            # Interpret the result
            if self.element_exists(LOC_NOT_FOUND):
                result.status = "Not in database"
                result.details = "No result found!"
            elif self.element_exists(LOC_SPAM_TEXT):
                result.status = "Spam"
                spam_text = self.get_element_text(LOC_SPAM_TEXT)
                if spam_text:
                    result.details = spam_text
            else:
                name = self.get_element_text(LOC_NAME_TEXT)
                result.status = "Safe"
                if name:
                    result.details = name

            # Return to input screen
            self.d.press("back")
            self.wait_for_element(LOC_INPUT_FIELD, timeout=3)

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
    Command-line interface for GetContact checker.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Check phone numbers using GetContact")
    parser.add_argument('-i', '--input', type=Path, required=True, help="File with phone numbers")
    parser.add_argument('-o', '--output', type=Path, default=Path('results_getcontact.csv'), help="Output CSV file")
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
        checker = GetContactChecker(args.device)
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
