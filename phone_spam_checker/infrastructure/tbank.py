import logging
import re
from typing import Optional

import requests

from ..domain.models import PhoneCheckResult, CheckStatus
from ..domain.phone_checker import PhoneChecker

logger = logging.getLogger(__name__)


class TbankChecker(PhoneChecker):
    """Checker using tbank.ru web service."""

    BASE_URL = "https://www.tbank.ru/oleg/who-called/info"

    def launch_app(self) -> bool:
        return True  # No initialization needed

    def close_app(self) -> None:
        pass

    def check_number(self, phone: str) -> PhoneCheckResult:
        logger.info("Checking number via Tbank: %s", phone)
        result = PhoneCheckResult(phone_number=phone, status=CheckStatus.UNKNOWN)
        try:
            url = f"{self.BASE_URL}/{phone}/"
            resp = requests.get(url, timeout=5)

            def looks_mojibake(s: str) -> bool:
                return "Ð" in s and "Ñ" in s

            encodings = [
                resp.encoding,
                getattr(resp, "apparent_encoding", None),
                "utf-8",
                "cp1251",
                "latin1",
            ]

            text = None
            for enc in encodings:
                if not enc:
                    continue
                try:
                    candidate = resp.content.decode(enc)
                except Exception:
                    continue
                if looks_mojibake(candidate):
                    continue
                text = candidate
                break

            if text is None:
                text = resp.content.decode("utf-8", errors="ignore")

            # service sometimes returns text with unicode escapes
            if "\\u" in text:
                try:
                    text = text.encode("latin1").decode("unicode_escape")
                except Exception:
                    pass
            match = re.search(
                r"<div[^>]*>(Номер\s+8.*?вероятно, принадлежит.*?)(</div>|$)",
                text,
                re.I,
            )
            if not match or not match.group(1):
                result.status = CheckStatus.NOT_IN_DB
            elif re.search(r"спам", match.group(1), re.I):
                result.status = CheckStatus.SPAM
                result.details = match.group(1).strip()
            else:
                result.status = CheckStatus.SAFE
                result.details = match.group(1).strip()
        except Exception as exc:
            logger.error("Tbank check error for %s: %s", phone, exc)
            result.status = CheckStatus.ERROR
            result.details = str(exc)
        return result
