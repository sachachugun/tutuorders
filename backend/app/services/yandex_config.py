"""Единая проверка настроек YandexGPT: .env + folder_id из таблицы settings."""

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting


def resolve_yandex_folder_id(db: Session | None = None) -> str:
    env_value = (settings.yandex_folder_id or "").strip()
    if env_value:
        return env_value
    if db is not None:
        row = db.get(Setting, "folder_id")
        if row and (row.value or "").strip():
            return row.value.strip()
    return ""


def resolve_yandex_model_name(db: Session | None = None) -> str:
    if db is not None:
        row = db.get(Setting, "model_name")
        if row and (row.value or "").strip():
            return row.value.strip()
    return (settings.yandex_model_name or "yandexgpt-pro").strip()


def yandex_api_key_configured() -> bool:
    return bool((settings.yandex_api_key or "").strip())


def yandex_configured(db: Session | None = None) -> bool:
    return yandex_api_key_configured() and bool(resolve_yandex_folder_id(db))


def yandex_config_status(db: Session | None = None) -> dict:
    folder_id = resolve_yandex_folder_id(db)
    return {
        "api_key_configured": yandex_api_key_configured(),
        "folder_id_configured": bool(folder_id),
        "configured": yandex_configured(db),
        "model_name": resolve_yandex_model_name(db),
    }
