import argparse
import logging
from pathlib import Path

import uiautomator2 as u2

from ..domain.models import PhoneCheckResult
from ..domain.phone_checker import PhoneChecker
from ..utils import read_phone_list, write_results
from ..logging_config import configure_logging

APP_PACKAGE = "app.source.getcontact"
APP_ACTIVITY = ".ui.starter.StarterActivity"

LOC_SEARCH_HINT = {"resourceId": "view.newsfeed.search.unfocus.searchhint"}
LOC_INPUT_FIELD = {"resourceId": "view.newsfeed.search.focus.searchfield"}

LOC_NOT_FOUND = {"resourceId": "view.numberdetail.profile.notFoundDisplayNameText"}
LOC_NAME_TEXT = {"resourceId": "view.numberdetail.profile.displayNameText"}
LOC_SPAM_TEXT = {"textContains": "Spam"}

LOC_LIMIT_DIALOG_CANCEL = {
    "resourceId": "ConfirmationDialogNegativeButton",
    "text": "CANCEL",
}
LOC_PRIVATE_MODE = {"resourceId": "dialog.privateModeSettings.title"}

configure_logging()
logger = logging.getLogger(__name__)


class GetContactChecker(PhoneChecker):
    def __init__(self, device: str) -> None:
        super().__init__(device)
        logger.info(f"Connecting to device {device}")
        self.d = u2.connect(device)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    def launch_app(self) -> bool:
        logger.info("Launching GetContact")
        try:
            self.d.app_start(APP_PACKAGE, activity=APP_ACTIVITY)
        except Exception as e:
            logger.error(f"Failed to launch GetContact: {e}")
            return False

        if not self.d(**LOC_SEARCH_HINT).wait(timeout=8):
            logger.error("Search hint did not appear")
            return False

        self.d(**LOC_SEARCH_HINT).click()
        if not self.d(**LOC_INPUT_FIELD).wait(timeout=3):
            logger.error("Input field did not appear after clicking search hint")
            return False
        return True

    def close_app(self) -> None:
        logger.info("Closing GetContact")
        self.d.app_stop(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
        if not phone.startswith("+"):
            phone = f"+{phone}"

        logger.info(f"Checking number: {phone}")
        result = PhoneCheckResult(phone_number=phone, status="Unknown")

        try:
            inp = self.d(**LOC_INPUT_FIELD)
            if not inp.wait(timeout=5):
                raise RuntimeError("Input field not available")

            inp.click()
            inp.clear_text()
            inp.set_text(phone)
            self.d.press("enter")

            if self.d(**LOC_LIMIT_DIALOG_CANCEL).exists(timeout=2):
                logger.info("Limit dialog detected -> pressing CANCEL")
                self.d(**LOC_LIMIT_DIALOG_CANCEL).click()

            if self.d(**LOC_PRIVATE_MODE).exists(timeout=1):
                logger.info("Private-mode dialog detected -> pressing BACK")
                self.d.press("back")

            cond_found = (
                self.d(**LOC_NOT_FOUND).wait(timeout=8)
                or self.d(**LOC_NAME_TEXT).exists
                or self.d(**LOC_SPAM_TEXT).exists
            )
            if not cond_found:
                raise RuntimeError("Result screen did not load")

            if self.d(**LOC_NOT_FOUND).exists:
                result.status = "Not in database"
                result.details = "No result found!"
            elif self.d(**LOC_SPAM_TEXT).exists:
                result.status = "Spam"
                result.details = self.d(**LOC_SPAM_TEXT).get_text()
            else:
                name = self.d(**LOC_NAME_TEXT).get_text()
                result.status = "Safe"
                result.details = name

            self.d.press("back")
            inp.wait(timeout=3)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} -> {result.status}")
        return result





def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phone number lookup via GetContact"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Input file with phone numbers",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results_getcontact.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "-d",
        "--device",
        type=str,
        default="127.0.0.1:5555",
        help="Android device ID",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"Loaded {len(phones)} numbers from {args.input}")

    checker = GetContactChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]
    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Results saved to {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
