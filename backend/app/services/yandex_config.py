"""Единая проверка настроек YandexGPT: .env + folder_id из таблицы settings."""

import os

from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, ENV_FILES, settings
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


def yandex_env_diagnostics() -> dict:
    """Без секретов: помогает понять, почему .env не подхватился на VPS."""
    backend_env = BACKEND_DIR / ".env"
    root_env = BACKEND_DIR.parent / ".env"
    api_in_os = "YANDEX_API_KEY" in os.environ
    folder_in_os = "YANDEX_FOLDER_ID" in os.environ
    return {
        "backend_dir": str(BACKEND_DIR),
        "env_files": list(ENV_FILES),
        "backend_env_exists": backend_env.is_file(),
        "root_env_exists": root_env.is_file(),
        "yandex_api_key_in_os_env": api_in_os,
        "yandex_folder_id_in_os_env": folder_in_os,
        "yandex_api_key_os_nonempty": bool((os.environ.get("YANDEX_API_KEY") or "").strip()),
        "yandex_folder_id_os_nonempty": bool((os.environ.get("YANDEX_FOLDER_ID") or "").strip()),
    }


def yandex_config_status(db: Session | None = None) -> dict:
    folder_id = resolve_yandex_folder_id(db)
    return {
        "api_key_configured": yandex_api_key_configured(),
        "folder_id_configured": bool(folder_id),
        "configured": yandex_configured(db),
        "model_name": resolve_yandex_model_name(db),
        "env": yandex_env_diagnostics(),
    }
