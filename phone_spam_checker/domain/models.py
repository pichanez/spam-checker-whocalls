from dataclasses import dataclass

@dataclass
class PhoneCheckResult:
    """Result of phone number verification."""
    phone_number: str
    status: str
    details: str = ""
