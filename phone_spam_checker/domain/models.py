from dataclasses import dataclass
from enum import Enum


class CheckStatus(str, Enum):
    """Possible verification outcomes."""

    UNKNOWN = "Unknown"
    NOT_IN_DB = "Not in database"
    SPAM = "Spam"
    SAFE = "Safe"
    ERROR = "Error"

@dataclass
class PhoneCheckResult:
    """Result of phone number verification."""
    phone_number: str
    status: CheckStatus
    details: str = ""
