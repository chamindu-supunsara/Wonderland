from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    mock_payments_enabled: bool = False
    booking_url: str = "http://127.0.0.1:8002"
    app_name: str = "Wonderland MOCK Payment"
    # Empty by default: configure explicitly; never use a fallback demo database in production.
    database_url: SecretStr = Field(
        validation_alias=AliasChoices("PAYMENT_DATABASE_URL", "DATABASE_URL")
    )
    cors_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    cognito_region: str = "ap-south-1"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""

    @property
    def auth_configured(self) -> bool:
        return bool(self.cognito_user_pool_id and self.cognito_app_client_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
