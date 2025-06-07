import logging
import sys
import json
from logging.handlers import RotatingFileHandler, SocketHandler


class JsonFormatter(logging.Formatter):
    """Format log records as JSON strings."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        data = {
            "time": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_logging(
    *,
    level: str | int = logging.INFO,
    fmt: str | None = None,
    log_file: str | None = None,
    json_format: bool = False,
    max_bytes: int = 0,
    backup_count: int = 0,
    remote_host: str | None = None,
    remote_port: int = 0,
) -> None:
    """Configure root logger for the application.

    Parameters
    ----------
    level:
        Logging level as string or numeric constant.
    fmt:
        Format string for log messages.
    log_file:
        Optional path to a file where logs should also be written.
    json_format:
        If ``True`` use JSON formatted logs.
    max_bytes:
        Maximum size of ``log_file`` before rotation.
    backup_count:
        Number of rotated files to keep.
    remote_host:
        Optional remote logging host.
    remote_port:
        Port for the remote logging host.
    """
    if logging.getLogger().handlers:
        return

    log_level = level
    if isinstance(level, str):
        log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = fmt or "%(asctime)s %(levelname)s %(name)s: %(message)s"
    if json_format:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        if max_bytes > 0:
            handlers.append(
                RotatingFileHandler(
                    log_file, maxBytes=max_bytes, backupCount=backup_count
                )
            )
        else:
            handlers.append(logging.FileHandler(log_file))
    if remote_host:
        handlers.append(SocketHandler(remote_host, remote_port))

    for h in handlers:
        h.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    for h in handlers:
        root.addHandler(h)
