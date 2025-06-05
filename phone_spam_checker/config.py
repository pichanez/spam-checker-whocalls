from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    api_key: str = ""
    kasp_adb_host: str = "127.0.0.1"
    kasp_adb_port: str = "5555"
    tc_adb_host: str = "127.0.0.1"
    tc_adb_port: str = "5556"
    gc_adb_host: str = "127.0.0.1"
    gc_adb_port: str = "5557"

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
