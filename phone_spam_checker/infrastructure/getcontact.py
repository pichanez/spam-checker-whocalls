import logging

from ..device_client import AndroidDeviceClient

from ..domain.models import PhoneCheckResult, CheckStatus
from ..domain.phone_checker import PhoneChecker

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

logger = logging.getLogger(__name__)


class GetContactChecker(PhoneChecker):
    def __init__(self, device: str) -> None:
        super().__init__(device)
        self.client = AndroidDeviceClient(device)
        self.d = self.client.d

    def launch_app(self) -> bool:
        logger.info("Launching GetContact")
        if not self.client.start_app(APP_PACKAGE, APP_ACTIVITY):
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
        self.client.stop_app(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
        if not phone.startswith("+"):
            phone = f"+{phone}"

        logger.info(f"Checking number: {phone}")
        result = PhoneCheckResult(phone_number=phone, status=CheckStatus.UNKNOWN)

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
                result.status = CheckStatus.NOT_IN_DB
                result.details = "No result found!"
            elif self.d(**LOC_SPAM_TEXT).exists:
                result.status = CheckStatus.SPAM
                result.details = self.d(**LOC_SPAM_TEXT).get_text()
            else:
                name = self.d(**LOC_NAME_TEXT).get_text()
                result.status = CheckStatus.SAFE
                result.details = name

            self.d.press("back")
            inp.wait(timeout=3)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = CheckStatus.ERROR
            result.details = str(e)

        logger.info(f"{phone} -> {result.status}")
        return result




