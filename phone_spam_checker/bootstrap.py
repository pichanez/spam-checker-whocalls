from .logging_config import configure_logging
from .registry import register_default_checkers, load_checker_module
from .config import settings


def initialize() -> None:
    """Configure logging and register available phone checkers."""
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        log_file=settings.log_file,
    )
    register_default_checkers()
    for mod in filter(None, getattr(settings, "checker_modules", [])):
        load_checker_module(mod)
