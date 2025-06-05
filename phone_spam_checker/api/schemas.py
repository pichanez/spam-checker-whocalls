from typing import List, Optional

from pydantic import BaseModel, field_validator

from phone_spam_checker.domain.models import CheckStatus
from phone_spam_checker.validators import validate_phone_number


class CheckRequest(BaseModel):
    numbers: List[str]
    service: str = "auto"  # 'auto', 'kaspersky', 'truecaller', 'getcontact'

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: List[str]) -> List[str]:
        return [validate_phone_number(num) for num in v]


class JobResponse(BaseModel):
    job_id: str


class CheckResult(BaseModel):
    phone_number: str
    status: CheckStatus
    details: str = ""


class StatusResponse(BaseModel):
    job_id: str
    status: str
    results: Optional[List[CheckResult]] = None
    error: Optional[str] = None
