import logging

from .base_checker import AndroidAppChecker

from ..domain.models import PhoneCheckResult, CheckStatus

APP_PACKAGE = "com.kaspersky.who_calls"
APP_ACTIVITY = "com.kaspersky.who_calls.LauncherActivityAlias"

LOC_BTN_CHECK_NUMBER = {"description": "Check number"}
LOC_INPUT_FIELD = {"className": "android.widget.EditText"}
LOC_BTN_DO_CHECK = {"text": "Check"}
LOC_NO_FEEDBACK_TEXT = {"text": "No feedback on the number"}
LOC_BTN_CANCEL = {"resourceId": "android:id/button2"}
LOC_SPAM_TEXT = {"textContains": "SPAM!"}
LOC_USEFUL_TEXT = {"textContains": "useful"}

logger = logging.getLogger(__name__)


class KasperskyWhoCallsChecker(AndroidAppChecker):

    def launch_app(self) -> bool:
        logger.info("Launching Kaspersky WhoCalls")
        if not self.client.start_app(APP_PACKAGE, APP_ACTIVITY):
            return False

        btn = self.d(**LOC_BTN_CHECK_NUMBER)
        if not btn.wait(timeout=2):
            logger.error("Check number button did not appear")
            return False
        btn.click()

        if not self.d(**LOC_INPUT_FIELD).wait(timeout=4):
            logger.error("Input field did not appear after 'Check number'")
            return False
        return True

    def close_app(self) -> None:
        logger.info("Closing application")
        self.client.stop_app(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
        logger.info(f"Checking number: {phone}")
        result = PhoneCheckResult(phone_number=phone, status=CheckStatus.UNKNOWN)

        try:
            inp = self.d(**LOC_INPUT_FIELD)
            if not inp.wait(timeout=2):
                raise RuntimeError("Input field not available")
            inp.click()
            inp.clear_text()
            inp.set_text(phone)

            btn_check = self.d(**LOC_BTN_DO_CHECK)
            if not btn_check.wait(timeout=2):
                raise RuntimeError("Check button did not appear")
            btn_check.click()

            if self.d(**LOC_NO_FEEDBACK_TEXT).exists(timeout=2):
                logger.info("Number not found — closing popup")
                cancel = self.d(**LOC_BTN_CANCEL)
                if cancel.wait(timeout=3):
                    cancel.click()
                result.status = CheckStatus.NOT_IN_DB
            else:
                if self.d(**LOC_SPAM_TEXT).exists(timeout=2):
                    result.status = CheckStatus.SPAM
                elif self.d(**LOC_USEFUL_TEXT).exists(timeout=2):
                    result.status = CheckStatus.SAFE
                else:
                    result.status = CheckStatus.UNKNOWN

            self.d.press("back")
            if not inp.wait(timeout=2):
                self.d.press("back")
                inp.wait(timeout=2)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = CheckStatus.ERROR
            result.details = str(e)

        logger.info(f"{phone} \u2192 {result.status}")
        return result



