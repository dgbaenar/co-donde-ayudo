from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def required_text(value: Any) -> str:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("configuration value must not be empty")
    return value.strip()


class DatabaseSettings(BaseSettings):
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: Any) -> str:
        return required_text(value)


class ApplicationSettings(DatabaseSettings):
    app_base_url: str = Field(validation_alias="APP_BASE_URL")
    coordinator_access_key: SecretStr = Field(
        validation_alias="COORDINATOR_ACCESS_KEY"
    )
    app_session_secret: SecretStr = Field(validation_alias="APP_SESSION_SECRET")

    @field_validator(
        "app_base_url",
        "coordinator_access_key",
        "app_session_secret",
        mode="before",
    )
    @classmethod
    def validate_web_configuration(cls, value: Any) -> str:
        return required_text(value)

    @field_validator("app_base_url")
    @classmethod
    def validate_app_base_url(cls, value: str) -> str:
        try:
            parsed_url = urlparse(value)
            hostname = parsed_url.hostname
            parsed_url.port
        except ValueError as error:
            raise ValueError("APP_BASE_URL must be a valid HTTP(S) URL") from error
        if parsed_url.scheme not in {"http", "https"} or hostname is None:
            raise ValueError("APP_BASE_URL must be a valid HTTP(S) URL")
        return value

    @property
    def session_cookie_https_only(self) -> bool:
        return urlparse(self.app_base_url).scheme == "https"
