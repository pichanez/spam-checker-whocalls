"""Project configuration loaded from environment variables."""

from dataclasses import dataclass, field
import os


def _getenv(key: str, default: str) -> str:
    """Read environment variable in a case-insensitive manner."""
    return os.getenv(key, os.getenv(key.lower(), default))


@dataclass
class Settings:
    """Application configuration."""

    api_key: str = ""
    secret_key: str = ""
    kasp_adb_host: str = "127.0.0.1"
    kasp_adb_port: str = "5555"
    tc_adb_host: str = "127.0.0.1"
    tc_adb_port: str = "5556"
    gc_adb_host: str = "127.0.0.1"
    gc_adb_port: str = "5557"
    job_db_path: str = "jobs.sqlite"
    pg_host: str = ""
    pg_port: str = "5432"
    pg_db: str = "phonechecker"
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    log_file: str | None = None
    worker_count: int = 1
    checker_modules: list[str] = field(default_factory=list)

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=_getenv("API_KEY", ""),
            secret_key=_getenv("SECRET_KEY", ""),
            kasp_adb_host=_getenv("KASP_ADB_HOST", "127.0.0.1"),
            kasp_adb_port=_getenv("KASP_ADB_PORT", "5555"),
            tc_adb_host=_getenv("TC_ADB_HOST", "127.0.0.1"),
            tc_adb_port=_getenv("TC_ADB_PORT", "5556"),
            gc_adb_host=_getenv("GC_ADB_HOST", "127.0.0.1"),
            gc_adb_port=_getenv("GC_ADB_PORT", "5557"),
            job_db_path=_getenv("JOB_DB_PATH", "jobs.sqlite"),
            pg_host=_getenv("PG_HOST", ""),
            pg_port=_getenv("PG_PORT", "5432"),
            pg_db=_getenv("PG_DB", "phonechecker"),
            pg_user=_getenv("PG_USER", "postgres"),
            pg_password=_getenv("PG_PASSWORD", "postgres"),
            log_level=_getenv("LOG_LEVEL", "INFO"),
            log_format=_getenv(
                "LOG_FORMAT", "%(asctime)s %(levelname)s %(name)s: %(message)s"
            ),
            log_file=_getenv("LOG_FILE", "") or None,
            worker_count=int(_getenv("WORKER_COUNT", "1")),
            checker_modules=[m for m in _getenv("CHECKER_MODULES", "").split(",") if m],
        )


settings = Settings.from_env()
