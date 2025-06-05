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
    kasp_devices: list[str] = field(default_factory=list)
    tc_devices: list[str] = field(default_factory=list)
    gc_devices: list[str] = field(default_factory=list)
    use_redis: bool = False
    redis_host: str = "127.0.0.1"
    redis_port: str = "6379"

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        cfg = cls(
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
            kasp_devices=[d for d in _getenv("KASP_DEVICES", "").split(",") if d],
            tc_devices=[d for d in _getenv("TC_DEVICES", "").split(",") if d],
            gc_devices=[d for d in _getenv("GC_DEVICES", "").split(",") if d],
            use_redis=_getenv("USE_REDIS", "0") == "1",
            redis_host=_getenv("REDIS_HOST", "127.0.0.1"),
            redis_port=_getenv("REDIS_PORT", "6379"),
        )
        if not cfg.kasp_devices:
            cfg.kasp_devices = [f"{cfg.kasp_adb_host}:{cfg.kasp_adb_port}"]
        if not cfg.tc_devices:
            cfg.tc_devices = [f"{cfg.tc_adb_host}:{cfg.tc_adb_port}"]
        if not cfg.gc_devices:
            cfg.gc_devices = [f"{cfg.gc_adb_host}:{cfg.gc_adb_port}"]
        return cfg


settings = Settings.from_env()
if not settings.api_key or not settings.secret_key:
    raise RuntimeError("API_KEY and SECRET_KEY environment variables are required")
