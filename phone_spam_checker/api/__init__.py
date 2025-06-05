from fastapi import FastAPI

from phone_spam_checker.exceptions import DeviceConnectionError

from .routes import router
from .jobs import start_background_tasks, device_error_handler, exception_middleware
from .schemas import CheckResult
from phone_spam_checker.domain.models import CheckStatus
from . import jobs, auth  # re-export for convenience

app = FastAPI(title="Phone Checker API", version="2.0")

app.include_router(router)
app.add_event_handler("startup", start_background_tasks)
app.add_exception_handler(DeviceConnectionError, device_error_handler)
app.middleware("http")(exception_middleware)

__all__ = [
    "app",
    "CheckResult",
    "CheckStatus",
]
