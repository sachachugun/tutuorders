import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Price, Supplier
from app.services.match_service import YANDEX_URL, _extract_json_object, _loads_model_json, _name_match_score, _normalize_name, _safe_error_text
from app.services.procurement_ai_match_service import yandex_configured

logger = logging.getLogger(__name__)


def find_price_row(db: Session, supplier_id: int, name_in_price: str) -> Price | None:
    return db.scalar(
        select(Price).where(
            Price.supplier_id == supplier_id,
            Price.name_in_price == name_in_price,
        )
    )

SUGGEST_MIN_SCORE = 0.32
SUGGEST_PER_SUPPLIER = 8
AI_TOP_PRICES = 40


def _local_candidates_for_supplier(
    db: Session, supplier_id: int, needle: str, unit: str | None, limit: int
) -> list[dict]:
    prices = db.scalars(select(Price).where(Price.supplier_id == supplier_id)).all()
    scored: list[tuple[float, Price]] = []
    for row in prices:
        if unit and row.unit != unit:
            continue
        score = _name_match_score(needle, _normalize_name(row.name_in_price))
        if score >= SUGGEST_MIN_SCORE:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1].price))
    return [
        {
            "name_in_price": row.name_in_price,
            "unit": row.unit,
            "price": round(float(row.price), 2),
            "score": round(score, 3),
        }
        for score, row in scored[:limit]
    ]


def _ai_pick_prices(
    product_name: str,
    unit: str | None,
    suppliers_payload: list[dict],
) -> dict[int, list[str]]:
    if not yandex_configured():
        return {}
    body = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_model_name}/latest",
        "completionOptions": {"temperature": 0.0, "maxTokens": 3000},
        "messages": [
            {
                "role": "system",
                "text": (
                    "Для канонического продукта из заказа выбери подходящие строки из прайсов поставщиков. "
                    "Верни только JSON: "
                    '{"picks":[{"supplier_id":1,"names_in_price":["..."]}]} . '
                    "Если нет подходящих — пустой names_in_price."
                ),
            },
            {
                "role": "user",
                "text": json.dumps(
                    {"product_name": product_name, "unit": unit, "suppliers": suppliers_payload},
                    ensure_ascii=False,
                ),
            },
        ],
    }
    headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}
    try:
        with httpx.Client(timeout=settings.yandex_timeout_seconds) as client:
            response = client.post(YANDEX_URL, headers=headers, json=body)
        if response.status_code >= 400:
            return {}
        data = response.json()
        text = data["result"]["alternatives"][0]["message"]["text"]
        parsed = _loads_model_json(_extract_json_object(text))
    except Exception as exc:
        logger.warning("sku_suggest_ai failed: %s", exc)
        return {}

    result: dict[int, list[str]] = {}
    for row in parsed.get("picks") or []:
        if not isinstance(row, dict):
            continue
        try:
            sid = int(row.get("supplier_id"))
        except (TypeError, ValueError):
            continue
        names = [str(n).strip() for n in (row.get("names_in_price") or []) if str(n).strip()]
        if names:
            result[sid] = names[:3]
    return result


def suggest_skus_for_product_name(db: Session, product_name: str, unit: str | None = None) -> dict:
    needle = _normalize_name(product_name)
    if not needle:
        return {"product_name": product_name, "suppliers": [], "ai_used": False}

    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    supplier_blocks: list[dict] = []
    ai_used = False

    for supplier in suppliers:
        local = _local_candidates_for_supplier(db, supplier.id, needle, unit, SUGGEST_PER_SUPPLIER)
        supplier_blocks.append(
            {
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "candidates": local,
            }
        )

    weak = all(len(block["candidates"]) == 0 or block["candidates"][0]["score"] < 0.55 for block in supplier_blocks)
    if weak and yandex_configured():
        ai_payload = []
        for supplier in suppliers:
            prices = db.scalars(select(Price).where(Price.supplier_id == supplier.id)).all()
            scored_prices: list[tuple[float, Price]] = []
            for price in prices:
                if unit and price.unit != unit:
                    continue
                score = _name_match_score(needle, _normalize_name(price.name_in_price))
                if score >= 0.2:
                    scored_prices.append((score, price))
            scored_prices.sort(key=lambda item: (-item[0], item[1].price))
            ai_payload.append(
                {
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "prices": [
                        {"name_in_price": p.name_in_price, "unit": p.unit, "price": float(p.price)}
                        for _, p in scored_prices[:AI_TOP_PRICES]
                    ],
                }
            )
        ai_picks = _ai_pick_prices(product_name, unit, ai_payload)
        if ai_picks:
            ai_used = True
            prices_by_supplier: dict[int, dict[str, Price]] = {}
            for supplier in suppliers:
                rows = db.scalars(select(Price).where(Price.supplier_id == supplier.id)).all()
                prices_by_supplier[supplier.id] = {r.name_in_price: r for r in rows}
            for block in supplier_blocks:
                sid = block["supplier_id"]
                picked_names = ai_picks.get(sid) or []
                existing = {c["name_in_price"] for c in block["candidates"]}
                for name in picked_names:
                    if name in existing:
                        continue
                    price_row = prices_by_supplier.get(sid, {}).get(name)
                    if not price_row:
                        continue
                    block["candidates"].insert(
                        0,
                        {
                            "name_in_price": price_row.name_in_price,
                            "unit": price_row.unit,
                            "price": round(float(price_row.price), 2),
                            "score": 0.75,
                        },
                    )
                    existing.add(name)

    return {"product_name": product_name, "suppliers": supplier_blocks, "ai_used": ai_used}
