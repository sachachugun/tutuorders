from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Всегда ищем .env рядом с backend/, а не в текущей cwd (на VPS systemd часто стартует из /opt/tutuorders).
BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_CANDIDATES = (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env")
ENV_FILES = tuple(str(path) for path in _ENV_CANDIDATES if path.is_file()) or (str(BACKEND_DIR / ".env"),)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
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
