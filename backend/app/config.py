from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
