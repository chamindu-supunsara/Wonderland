from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )
    database_url: SecretStr = Field(
        validation_alias=AliasChoices("ADMISSION_DATABASE_URL", "DATABASE_URL")
    )
    mock_admission_enabled: bool = False
    events_topic_arn: str = ""
    booking_url: str = "http://127.0.0.1:8002"
    catalog_url: str = "http://127.0.0.1:8001"
    cors_origins: list[str] = ["http://127.0.0.1:4200", "http://localhost:4200"]
    cognito_region: str = "ap-south-1"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""

    @property
    def auth_configured(self):
        return bool(self.cognito_user_pool_id and self.cognito_app_client_id)


@lru_cache
def get_settings():
    return Settings()
