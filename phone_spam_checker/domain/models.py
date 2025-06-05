from dataclasses import dataclass
from enum import Enum
import re
from pydantic import BaseModel, field_validator


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


class PhoneInput(BaseModel):
    """Input model for phone numbers with validation."""

    number: str

    @field_validator("number")
    @classmethod
    def check_phone(cls, v: str) -> str:
        if not re.fullmatch(r"\+?\d{3,15}", v):
            raise ValueError("Invalid phone number format")
        return v
