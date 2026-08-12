from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.config import ApplicationSettings, DatabaseSettings


def application_settings(app_base_url: str) -> ApplicationSettings:
    return ApplicationSettings(
        DATABASE_URL="postgresql://example",
        APP_BASE_URL=app_base_url,
        COORDINATOR_ACCESS_KEY="synthetic-access-key",
        APP_SESSION_SECRET="synthetic-session-secret",
        _env_file=None,
    )


def test_database_settings_loads_database_url_from_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://synthetic:secret@localhost/donde_ayudo\n"
        "IGNORED_SETTING=ignored\n",
        encoding="utf-8",
    )

    settings = DatabaseSettings(_env_file=env_file)

    assert (
        settings.database_url.get_secret_value()
        == "postgresql://synthetic:secret@localhost/donde_ayudo"
    )


def test_database_settings_prefers_process_environment_over_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://file-value\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://process-value")

    settings = DatabaseSettings(_env_file=env_file)

    assert settings.database_url.get_secret_value() == "postgresql://process-value"


def test_database_settings_rejects_missing_or_blank_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        DatabaseSettings(_env_file=None)
    with pytest.raises(ValidationError):
        DatabaseSettings(DATABASE_URL="   ", _env_file=None)


def test_application_settings_loads_web_configuration_and_hides_secrets() -> None:
    settings = ApplicationSettings(
        DATABASE_URL="postgresql://db-user:db-password@localhost/donde_ayudo",
        APP_BASE_URL="https://dondeayudo.example",
        COORDINATOR_ACCESS_KEY="synthetic-access-key",
        APP_SESSION_SECRET="synthetic-session-secret",
        _env_file=None,
    )

    assert settings.app_base_url == "https://dondeayudo.example"
    assert (
        settings.coordinator_access_key.get_secret_value()
        == "synthetic-access-key"
    )
    assert settings.app_session_secret.get_secret_value() == "synthetic-session-secret"
    rendered = repr(settings)
    assert "db-password" not in rendered
    assert "synthetic-access-key" not in rendered
    assert "synthetic-session-secret" not in rendered


@pytest.mark.parametrize(
    "field_name",
    ["APP_BASE_URL", "COORDINATOR_ACCESS_KEY", "APP_SESSION_SECRET"],
)
def test_application_settings_rejects_blank_web_configuration(field_name: str) -> None:
    values = {
        "DATABASE_URL": "postgresql://example",
        "APP_BASE_URL": "https://dondeayudo.example",
        "COORDINATOR_ACCESS_KEY": "synthetic-access-key",
        "APP_SESSION_SECRET": "synthetic-session-secret",
        field_name: "   ",
    }

    with pytest.raises(ValidationError):
        ApplicationSettings(**values, _env_file=None)


@pytest.mark.parametrize(
    ("app_base_url", "https_only"),
    [
        ("https://dondeayudo.example", True),
        ("http://localhost:8080", False),
    ],
)
def test_application_settings_derives_session_cookie_security(
    app_base_url: str, https_only: bool
) -> None:
    settings = application_settings(app_base_url)

    assert settings.session_cookie_https_only is https_only


@pytest.mark.parametrize(
    "app_base_url",
    [
        "localhost:8080",
        "ftp://dondeayudo.example",
        "https://",
        "https://dondeayudo.example:not-a-port",
    ],
)
def test_application_settings_rejects_invalid_app_base_url(
    app_base_url: str,
) -> None:
    with pytest.raises(ValidationError):
        application_settings(app_base_url)
