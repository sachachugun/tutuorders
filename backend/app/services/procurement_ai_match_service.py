import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CanonicalProduct
from app.services.match_service import YANDEX_URL, _extract_json_object, _loads_model_json, _safe_error_text
from app.services.yandex_config import build_yandex_model_uri, yandex_configured

logger = logging.getLogger(__name__)


def ai_resolve_demand_to_products(db: Session, demand_names: list[str]) -> dict[str, int]:
    """
    Map demand names to canonical product ids via YandexGPT.
    Returns {normalized_demand_name: product_id} for confident matches only.
    """
    if not yandex_configured(db):
        return {}

    unique_names = []
    seen: set[str] = set()
    for name in demand_names:
        key = (name or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique_names.append(name.strip())

    if not unique_names:
        return {}

    products = db.scalars(select(CanonicalProduct).where(CanonicalProduct.is_active == 1).order_by(CanonicalProduct.name)).all()
    if not products:
        return {}

    payload = {
        "canonical_products": [{"id": p.id, "name": p.name, "unit": p.default_unit} for p in products],
        "demand_names": unique_names,
    }
    model_uri = build_yandex_model_uri(db)
    body = {
        "modelUri": model_uri,
        "completionOptions": {"temperature": 0.0, "maxTokens": 4000},
        "messages": [
            {
                "role": "system",
                "text": (
                    "Сопоставь названия из заказа с каноническими продуктами из словаря. "
                    "Учитывай синонимы, опечатки, единственное/множественное число (яблоко = яблоки). "
                    "Если уверенности нет — product_id: null. "
                    'Ответ: только JSON {"assignments":[{"demand_name":"...","product_id":123|null,"reason":"..."}]}'
                ),
            },
            {"role": "user", "text": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}

    try:
        with httpx.Client(timeout=settings.yandex_timeout_seconds) as client:
            response = client.post(YANDEX_URL, headers=headers, json=body)
        if response.status_code >= 400:
            logger.warning(
                "procurement_ai_match http %s model_uri=%s: %s",
                response.status_code,
                model_uri,
                _safe_error_text(response.text),
            )
            return {}
        data = response.json()
        text = data["result"]["alternatives"][0]["message"]["text"]
        parsed = _loads_model_json(_extract_json_object(text))
    except Exception as exc:
        logger.warning("procurement_ai_match failed: %s", exc)
        return {}

    valid_ids = {p.id for p in products}
    result: dict[str, int] = {}
    for row in parsed.get("assignments") or []:
        if not isinstance(row, dict):
            continue
        demand_name = str(row.get("demand_name") or "").strip()
        product_id = row.get("product_id")
        if not demand_name or product_id is None:
            continue
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            continue
        if pid in valid_ids:
            result[demand_name.lower()] = pid
    return result
