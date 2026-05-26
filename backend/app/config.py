from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

# Всегда ищем .env рядом с backend/, а не в текущей cwd (на VPS systemd часто стартует из /opt/tutuorders).
BACKEND_DIR = Path(__file__).resolve().parent.parent
# Сначала корень проекта, потом backend/.env — последний файл побеждает внутри dotenv.
_ENV_CANDIDATES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")
ENV_FILES = tuple(str(path) for path in _ENV_CANDIDATES if path.is_file()) or (str(BACKEND_DIR / ".env"),)


class IgnoreEmptyEnvSettingsSource(EnvSettingsSource):
    """Пустые YANDEX_* из systemd не должны блокировать значения из backend/.env."""

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            IgnoreEmptyEnvSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    app_name: str = "tutuorders"
    database_url: str = "sqlite:///./app.db"

    yandex_folder_id: str = ""
    yandex_model_name: str = "yandexgpt-pro"
    yandex_api_key: str = ""
    yandex_timeout_seconds: int = 25
    auth_enabled: bool = False
    auth_username: str = "admin"
    auth_password: str = "admin123"
    auth_secret: str = "change-me-please"
    auth_token_ttl_seconds: int = 28800


settings = Settings()
