import argparse
import logging
from pathlib import Path

from ..device_client import AndroidDeviceClient

from ..domain.models import PhoneCheckResult
from ..domain.phone_checker import PhoneChecker
from ..utils import read_phone_list, write_results
from ..logging_config import configure_logging
from ..config import settings

APP_PACKAGE = "com.truecaller"
APP_ACTIVITY = "com.truecaller.ui.TruecallerInit"

LOC_SEARCH_LABEL = {"resourceId": "com.truecaller:id/searchBarLabel"}
LOC_INPUT_FIELD = {"resourceId": "com.truecaller:id/search_field"}
LOC_SEARCH_WEB = {"resourceId": "com.truecaller:id/searchWeb"}
LOC_SPAM_TEXT = {"textContains": "SPAM"}
LOC_NAME_OR_NUMBER = {"resourceId": "com.truecaller:id/nameOrNumber"}
LOC_NUMBER_DETAILS = {"resourceId": "com.truecaller:id/numberDetails"}
LOC_PHONE_NUMBER = {"resourceId": "com.truecaller:id/phoneNumber"}

logger = logging.getLogger(__name__)


class TruecallerChecker(PhoneChecker):
    def __init__(self, device: str) -> None:
        super().__init__(device)
        self.client = AndroidDeviceClient(device)
        self.d = self.client.d

    def launch_app(self) -> bool:
        logger.info("Launching Truecaller")
        if not self.client.start_app(APP_PACKAGE, APP_ACTIVITY):
            return False

        lbl = self.d(**LOC_SEARCH_LABEL)
        if not lbl.wait(timeout=2):
            logger.error("Search label did not appear")
            return False
        lbl.click()

        if not self.d(**LOC_INPUT_FIELD).wait(timeout=2):
            logger.error("Input field did not appear after clicking search")
            return False
        return True

    def close_app(self) -> None:
        logger.info("Closing Truecaller")
        self.client.stop_app(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
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

            if not self.d(**LOC_PHONE_NUMBER).wait(timeout=5) and not self.d(**LOC_SPAM_TEXT).exists(timeout=5):
                raise RuntimeError("Result screen did not load")

            if self.d(**LOC_SEARCH_WEB).exists(timeout=2):
                logger.info("No entry in database — SEARCH THE WEB found")
                result.status = "Not in database"
            else:
                if self.d(**LOC_SPAM_TEXT).exists(timeout=3):
                    result.status = "Spam"
                else:
                    name_or_num = self.d(**LOC_NAME_OR_NUMBER).get_text()
                    details = ""
                    if self.d(**LOC_NUMBER_DETAILS).exists(timeout=2):
                        details = self.d(**LOC_NUMBER_DETAILS).get_text()
                    result.status = "Safe"
                    result.details = f"{name_or_num}; {details}" if details else name_or_num

            self.d.press("back")
            if not inp.wait(timeout=3):
                self.d.press("back")
                inp.wait(timeout=5)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} -> {result.status}")
        return result





def main() -> int:
    configure_logging(level=settings.log_level)

    parser = argparse.ArgumentParser(
        description="Phone number lookup via Truecaller"
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
        default=Path("results_truecaller.csv"),
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

    checker = TruecallerChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]
    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Results saved to {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
