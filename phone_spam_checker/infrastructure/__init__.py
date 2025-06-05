from .kaspersky import KasperskyWhoCallsChecker
from .truecaller import TruecallerChecker
from .getcontact import GetContactChecker
from ..registry import register_checker

register_checker("kaspersky", KasperskyWhoCallsChecker)
register_checker("truecaller", TruecallerChecker)
register_checker("getcontact", GetContactChecker)

__all__ = [
    "KasperskyWhoCallsChecker",
    "TruecallerChecker",
    "GetContactChecker",
]
