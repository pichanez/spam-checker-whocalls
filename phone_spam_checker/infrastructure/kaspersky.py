import argparse
import csv
import logging
from dataclasses import asdict
from pathlib import Path

import uiautomator2 as u2

from ..domain.models import PhoneCheckResult
from ..domain.phone_checker import PhoneChecker

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
        logger.info(f"\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0443 {device}")
        self.d = u2.connect(device)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    def launch_app(self) -> bool:
        logger.info("\u0417\u0430\u043f\u0443\u0441\u043a \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f")
        try:
            self.d.app_start(APP_PACKAGE, activity=APP_ACTIVITY)
        except Exception as e:
            logger.error(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435: {e}")
            return False

        btn = self.d(**LOC_BTN_CHECK_NUMBER)
        if not btn.wait(timeout=10):
            logger.error("\u041a\u043d\u043e\u043f\u043a\u0430 \u00abCheck number\u00bb \u043d\u0435 \u043f\u043e\u044f\u0432\u0438\u043b\u0430\u0441\u044c")
            return False
        btn.click()

        if not self.d(**LOC_INPUT_FIELD).wait(timeout=8):
            logger.error("\u041f\u043e\u043b\u0435 \u0432\u0432\u043e\u0434\u0430 \u043d\u0435 \u043f\u043e\u044f\u0432\u0438\u043b\u043e\u0441\u044c \u043f\u043e\u0441\u043b\u0435 \u00abCheck number\u00bb")
            return False
        return True

    def close_app(self) -> None:
        logger.info("\u0417\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f")
        self.d.app_stop(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
        logger.info(f"\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043d\u043e\u043c\u0435\u0440\u0430: {phone}")
        result = PhoneCheckResult(phone_number=phone, status="Unknown")

        try:
            inp = self.d(**LOC_INPUT_FIELD)
            if not inp.wait(timeout=5):
                raise RuntimeError("\u041f\u043e\u043b\u0435 \u0432\u0432\u043e\u0434\u0430 \u043d\u0435 \u043f\u043e\u044f\u0432\u0438\u043b\u043e\u0441\u044c")
            inp.click()
            inp.clear_text()
            inp.set_text(phone)

            btn_check = self.d(**LOC_BTN_DO_CHECK)
            if not btn_check.wait(timeout=5):
                raise RuntimeError("\u041a\u043d\u043e\u043f\u043a\u0430 \u00abCheck\u00bb \u043d\u0435 \u043f\u043e\u044f\u0432\u0438\u043b\u0430\u0441\u044c")
            btn_check.click()

            if self.d(**LOC_NO_FEEDBACK_TEXT).exists(timeout=4):
                logger.info("\u041d\u043e\u043c\u0435\u0440 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u2014 \u0437\u0430\u043a\u0440\u044b\u0432\u0430\u044e \u043f\u043e\u043f\u0430\u043f")
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
            logger.error(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0435 {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} \u2192 {result.status}")
        return result


def read_phone_list(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_results(path: Path, results: list[PhoneCheckResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["phone_number", "status", "details"])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def main() -> int:
    parser = argparse.ArgumentParser(description="\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0442\u0435\u043b\u0435\u0444\u043e\u043d\u043d\u044b\u0445 \u043d\u043e\u043c\u0435\u0440\u043e\u0432 \u0447\u0435\u0440\u0435\u0437 Kaspersky Who Calls")
    parser.add_argument("-i", "--input", type=Path, required=True, help="\u0424\u0430\u0439\u043b \u0441\u043e \u0441\u043f\u0438\u0441\u043a\u043e\u043c \u043d\u043e\u043c\u0435\u0440\u043e\u0432")
    parser.add_argument("-o", "--output", type=Path, default=Path("results.csv"), help="\u041a\u0443\u0434\u0430 \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b")
    parser.add_argument("-d", "--device", type=str, default="127.0.0.1:5555", help="ID Android-\u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0430")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"\u0412\u0445\u043e\u0434\u043d\u043e\u0439 \u0444\u0430\u0439\u043b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"\u0417\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043e {len(phones)} \u043d\u043e\u043c\u0435\u0440\u043e\u0432 \u0438\u0437 {args.input}")

    checker = KasperskyWhoCallsChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]

    checker.close_app()
    write_results(args.output, results)
    logger.info(f"\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b \u0432 {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
