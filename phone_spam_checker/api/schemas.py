from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from pydantic import BaseModel, field_validator

from phone_spam_checker.domain.models import CheckStatus
from phone_spam_checker.validators import validate_phone_number


class CheckRequest(BaseModel):
    numbers: List[str]
    # 'auto' – use kaspersky, getcontact and tbank for Russian numbers,
    # truecaller for others
    service: str = "auto"  # 'auto', 'kaspersky', 'truecaller', 'getcontact', 'tbank'

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: List[str]) -> List[str]:
        return [validate_phone_number(num) for num in v]


class JobResponse(BaseModel):
    job_id: str


class ServiceResult(BaseModel):
    service: str
    status: CheckStatus
    details: str = ""

    model_config = ConfigDict(use_enum_values=True)


class CheckResult(BaseModel):
    phone_number: str
    status: CheckStatus
    details: str = ""
    services: Optional[List[ServiceResult]] = None

    model_config = ConfigDict(use_enum_values=True)


class StatusResponse(BaseModel):
    job_id: str
    status: str
    results: Optional[List[CheckResult]] = None
    error: Optional[str] = None
