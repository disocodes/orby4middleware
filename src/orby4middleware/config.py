from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORBY_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./orby4middleware.db"
    api_key: str = "change-me-before-production"
    raw_retention_enabled: bool = True
    delivery_timeout_seconds: int = 15
    default_fhir_base_url: str | None = None
    default_rest_result_url: str | None = None
    default_hl7_host: str | None = None
    default_hl7_port: int = 2575


@lru_cache
def get_settings() -> Settings:
    return Settings()
