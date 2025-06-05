"""Project configuration loaded from environment variables."""

from dataclasses import dataclass
import os


def _getenv(key: str, default: str) -> str:
    """Read environment variable in a case-insensitive manner."""
    return os.getenv(key, os.getenv(key.lower(), default))


@dataclass
class Settings:
    """Application configuration."""

    api_key: str = ""
    kasp_adb_host: str = "127.0.0.1"
    kasp_adb_port: str = "5555"
    tc_adb_host: str = "127.0.0.1"
    tc_adb_port: str = "5556"
    gc_adb_host: str = "127.0.0.1"
    gc_adb_port: str = "5557"
    job_db_path: str = "jobs.sqlite"
    log_level: str = "INFO"
    log_file: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=_getenv("API_KEY", ""),
            kasp_adb_host=_getenv("KASP_ADB_HOST", "127.0.0.1"),
            kasp_adb_port=_getenv("KASP_ADB_PORT", "5555"),
            tc_adb_host=_getenv("TC_ADB_HOST", "127.0.0.1"),
            tc_adb_port=_getenv("TC_ADB_PORT", "5556"),
            gc_adb_host=_getenv("GC_ADB_HOST", "127.0.0.1"),
            gc_adb_port=_getenv("GC_ADB_PORT", "5557"),
            job_db_path=_getenv("JOB_DB_PATH", "jobs.sqlite"),
            log_level=_getenv("LOG_LEVEL", "INFO"),
            log_file=_getenv("LOG_FILE", "") or None,
        )
settings = Settings.from_env()
