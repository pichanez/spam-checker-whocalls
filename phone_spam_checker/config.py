"""Project configuration loaded from environment variables."""

from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(case_sensitive=False)

    api_key: str
    secret_key: str
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
    token_ttl_hours: int = 1
    checker_modules: List[str] = []
    kasp_devices: List[str] = []
    tc_devices: List[str] = []
    gc_devices: List[str] = []
    use_redis: bool = False
    redis_host: str = "127.0.0.1"
    redis_port: str = "6379"

    @field_validator(
        "checker_modules",
        "kasp_devices",
        "tc_devices",
        "gc_devices",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [item for item in v.split(",") if item]
        return list(v) if v else []

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        if not self.kasp_devices:
            self.kasp_devices = [f"{self.kasp_adb_host}:{self.kasp_adb_port}"]
        if not self.tc_devices:
            self.tc_devices = [f"{self.tc_adb_host}:{self.tc_adb_port}"]
        if not self.gc_devices:
            self.gc_devices = [f"{self.gc_adb_host}:{self.gc_adb_port}"]

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )


try:
    settings = Settings()
except Exception as exc:  # ValidationError or others
    raise RuntimeError(
        "API_KEY and SECRET_KEY environment variables are required"
    ) from exc

if not settings.api_key or not settings.secret_key:
    raise RuntimeError("API_KEY and SECRET_KEY environment variables are required")
