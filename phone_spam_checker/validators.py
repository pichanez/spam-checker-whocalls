from .domain.models import PhoneInput


def validate_phone_number(value: str) -> str:
    """Validate and return the phone number."""
    return PhoneInput(number=value).number

