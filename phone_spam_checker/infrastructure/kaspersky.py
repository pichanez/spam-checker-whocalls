import argparse
import logging
from pathlib import Path

import uiautomator2 as u2

from ..domain.models import PhoneCheckResult
from ..domain.phone_checker import PhoneChecker
from ..utils import read_phone_list, write_results

APP_PACKAGE = "com.kaspersky.who_calls"
APP_ACTIVITY = "com.kaspersky.who_calls.LauncherActivityAlias"

LOC_BTN_CHECK_NUMBER = {"description": "Check number"}
LOC_INPUT_FIELD = {"className": "android.widget.EditText"}
LOC_BTN_DO_CHECK = {"text": "Check"}
LOC_NO_FEEDBACK_TEXT = {"text": "No feedback on the number"}
LOC_BTN_CANCEL = {"resourceId": "android:id/button2"}
LOC_SPAM_TEXT = {"textContains": "SPAM!"}
LOC_USEFUL_TEXT = {"textContains": "useful"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class KasperskyWhoCallsChecker(PhoneChecker):
    def __init__(self, device: str) -> None:
        super().__init__(device)
        logger.info(f"Connected to device {device}")
        self.d = u2.connect(device)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    def launch_app(self) -> bool:
        logger.info("Launching application")
        try:
            self.d.app_start(APP_PACKAGE, activity=APP_ACTIVITY)
        except Exception as e:
            logger.error(f"Failed to launch application: {e}")
            return False

        btn = self.d(**LOC_BTN_CHECK_NUMBER)
        if not btn.wait(timeout=10):
            logger.error("Check number button did not appear")
            return False
        btn.click()

        if not self.d(**LOC_INPUT_FIELD).wait(timeout=8):
            logger.error("Input field did not appear after 'Check number'")
            return False
        return True

    def close_app(self) -> None:
        logger.info("Closing application")
        self.d.app_stop(APP_PACKAGE)

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

            btn_check = self.d(**LOC_BTN_DO_CHECK)
            if not btn_check.wait(timeout=5):
                raise RuntimeError("Check button did not appear")
            btn_check.click()

            if self.d(**LOC_NO_FEEDBACK_TEXT).exists(timeout=4):
                logger.info("Number not found — closing popup")
                cancel = self.d(**LOC_BTN_CANCEL)
                if cancel.wait(timeout=3):
                    cancel.click()
                result.status = "Not in database"
            else:
                if self.d(**LOC_SPAM_TEXT).exists(timeout=4):
                    result.status = "Spam"
                elif self.d(**LOC_USEFUL_TEXT).exists(timeout=4):
                    result.status = "Safe"
                else:
                    result.status = "Unknown"

            self.d.press("back")
            if not inp.wait(timeout=5):
                self.d.press("back")
                inp.wait(timeout=5)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} \u2192 {result.status}")
        return result





def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phone number lookup via Kaspersky Who Calls"
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
        default=Path("results.csv"),
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

    checker = KasperskyWhoCallsChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]

    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Results saved to {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
