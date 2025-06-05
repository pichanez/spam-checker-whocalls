import logging
import sys


def configure_logging(*, level: str | int = logging.INFO, fmt: str | None = None, log_file: str | None = None) -> None:
    """Configure root logger for the application.

    Parameters
    ----------
    level:
        Logging level as string or numeric constant.
    fmt:
        Format string for log messages.
    log_file:
        Optional path to a file where logs should also be written.
    """
    if logging.getLogger().handlers:
        return

    log_level = level
    if isinstance(level, str):
        log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = fmt or "%(asctime)s %(levelname)s %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
