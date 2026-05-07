import json
import logging
import time
import re

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Price, Supplier
from app.parsers.order_parser import parse_order_text

logger = logging.getLogger(__name__)
YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def _safe_error_text(raw: str, limit: int = 300) -> str:
    text = (raw or "").replace("\n", " ").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _extract_json_object(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _loads_model_json(raw_text: str) -> dict:
    candidate = _extract_json_object(raw_text)
    return json.loads(candidate)


def _build_input_payload(parsed_items: list[dict], suppliers: list[Supplier], prices: list[Price]) -> dict:
    prices_by_supplier: dict[int, list[dict]] = {}
    for supplier in suppliers:
        prices_by_supplier[supplier.id] = []
    for price in prices:
        prices_by_supplier[price.supplier_id].append(
            {"name_in_price": price.name_in_price, "unit": price.unit, "price": round(float(price.price), 2)}
        )
    return {
        "order_items": parsed_items,
        "suppliers": [{"supplier_id": s.id, "name": s.name} for s in suppliers],
        "prices": prices_by_supplier,
    }


def _normalize_name(value: str) -> str:
    text = " ".join((value or "").strip().lower().split())
    text = text.rstrip("-–—:;, ")
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("ё", "е")
    text = " ".join(text.split())
    return text


def _ensure_all_items_present(parsed_items: list[dict], model_items: list[dict]) -> list[dict]:
    existing_keys = {
        (_normalize_name(item.get("canonical_name", "")), float(item.get("quantity", 0)), item.get("unit", ""))
        for item in model_items
    }
    completed = list(model_items)
    for parsed in parsed_items:
        key = (_normalize_name(parsed["name"]), float(parsed["quantity"]), parsed["unit"])
        if key in existing_keys:
            continue
        completed.append(
            {
                "canonical_name": parsed["name"],
                "quantity": parsed["quantity"],
                "unit": parsed["unit"],
                "matches": [],
                "warning": "Позиция не возвращена моделью",
            }
        )
    return completed


def _attach_db_fallback_matches(items: list[dict], prices: list[Price], suppliers: list[Supplier]) -> list[dict]:
    by_supplier: dict[int, list[Price]] = {s.id: [] for s in suppliers}
    for price in prices:
        by_supplier.setdefault(price.supplier_id, []).append(price)

    for item in items:
        if item.get("matches"):
            continue
        needle = _normalize_name(str(item.get("canonical_name", "")))
        if not needle:
            continue

        fallback_matches = []
        for supplier in suppliers:
            best_price: Price | None = None
            for candidate in by_supplier.get(supplier.id, []):
                hay = _normalize_name(candidate.name_in_price)
                if not hay:
                    continue
                # MVP fallback: exact/containment match from DB price lines.
                if needle == hay or needle in hay or hay in needle:
                    if best_price is None or float(candidate.price) < float(best_price.price):
                        best_price = candidate
            if best_price is not None:
                fallback_matches.append(
                    {
                        "supplier_id": supplier.id,
                        "name_in_price": best_price.name_in_price,
                        "price": round(float(best_price.price), 2),
                        "note": "fallback db match",
                    }
                )

        if fallback_matches:
            item["matches"] = fallback_matches
            if not item.get("warning"):
                item["warning"] = "Сопоставлено по fallback-правилу"
    return items


def _call_yandex_gpt(payload: dict) -> dict:
    if not settings.yandex_api_key or not settings.yandex_folder_id:
        raise HTTPException(status_code=500, detail="Обратитесь к разработчику")
    body = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_model_name}/latest",
        "completionOptions": {"temperature": 0.1, "maxTokens": 4000},
        "messages": [
            {
                "role": "system",
                "text": (
                    "Верни только валидный JSON без markdown, без пояснений, без кода в тройных кавычках. Формат: "
                    '{"items":[{"canonical_name":"string","quantity":0,"unit":"кг|г|л|мл","matches":[{"supplier_id":0,'
                    '"name_in_price":"string","price":0,"note":null}],"warning":null}]}'
                ),
            },
            {"role": "user", "text": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}

    try:
        with httpx.Client(timeout=settings.yandex_timeout_seconds) as client:
            response = client.post(YANDEX_URL, headers=headers, json=body)
    except httpx.TimeoutException:
        logger.error("yandex_gpt_timeout timeout_seconds=%s", settings.yandex_timeout_seconds)
        raise HTTPException(status_code=502, detail="YandexGPT timeout: Обратитесь к разработчику")
    except httpx.HTTPError as exc:
        logger.error("yandex_gpt_http_error error=%s", str(exc))
        raise HTTPException(status_code=502, detail="YandexGPT HTTP error: Обратитесь к разработчику")
    if response.status_code >= 400:
        body_excerpt = _safe_error_text(response.text)
        logger.error("yandex_gpt_failed status=%s body=%s", response.status_code, body_excerpt)
        raise HTTPException(status_code=502, detail=f"YandexGPT {response.status_code}: {body_excerpt}")
    data = response.json()
    try:
        text = data["result"]["alternatives"][0]["message"]["text"]
    except (KeyError, IndexError, TypeError):
        logger.error("yandex_gpt_unexpected_response body=%s", _safe_error_text(json.dumps(data, ensure_ascii=False)))
        raise HTTPException(status_code=502, detail="YandexGPT returned unexpected response format")
    return _parse_model_json_with_retry(text, payload)


def _parse_model_json_with_retry(raw_text: str, payload: dict) -> dict:
    try:
        return _loads_model_json(raw_text)
    except json.JSONDecodeError:
        body = {
            "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_model_name}/latest",
            "completionOptions": {"temperature": 0.1, "maxTokens": 4000},
            "messages": [
                {
                    "role": "system",
                    "text": (
                        "Ответ должен содержать только JSON-объект. "
                        "Без markdown, без текста до/после JSON, без ```json."
                    ),
                },
                {"role": "user", "text": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}
        try:
            with httpx.Client(timeout=settings.yandex_timeout_seconds) as client:
                retry_response = client.post(YANDEX_URL, headers=headers, json=body)
        except httpx.HTTPError as exc:
            logger.error("yandex_gpt_retry_http_error error=%s", str(exc))
            raise HTTPException(status_code=502, detail="YandexGPT retry HTTP error: Обратитесь к разработчику")
        if retry_response.status_code >= 400:
            body_excerpt = _safe_error_text(retry_response.text)
            logger.error("yandex_gpt_retry_failed status=%s body=%s", retry_response.status_code, body_excerpt)
            raise HTTPException(status_code=502, detail=f"YandexGPT retry {retry_response.status_code}: {body_excerpt}")
        retry_data = retry_response.json()
        try:
            retry_text = retry_data["result"]["alternatives"][0]["message"]["text"]
            return _loads_model_json(retry_text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            logger.error(
                "yandex_gpt_retry_invalid_json body=%s",
                _safe_error_text(json.dumps(retry_data, ensure_ascii=False)),
            )
            raise HTTPException(status_code=502, detail="YandexGPT returned invalid JSON twice")


def _compute_result(model_result: dict, suppliers: list[Supplier]) -> tuple[list[dict], list[dict]]:
    supplier_totals = {supplier.id: 0.0 for supplier in suppliers}
    result_items: list[dict] = []
    for item in model_result.get("items", []):
        quantity = float(item.get("quantity", 0))
        matches = item.get("matches") or []
        sorted_matches = sorted(matches, key=lambda m: float(m.get("price", 0)) if float(m.get("price", 0)) > 0 else 10**9)
        allocation = []
        row_total = 0.0
        if sorted_matches:
            best = sorted_matches[0]
            for match in sorted_matches:
                supplier_id = int(match["supplier_id"])
                allocated_qty = quantity if match is best else 0.0
                amount = round(float(match.get("price", 0)) * allocated_qty, 2)
                allocation.append({"supplier_id": supplier_id, "quantity": round(allocated_qty, 3), "amount": amount})
                supplier_totals[supplier_id] += amount
                row_total += amount
        result_items.append(
            {
                "canonical_name": item.get("canonical_name"),
                "quantity": round(quantity, 3),
                "unit": item.get("unit"),
                "warning": item.get("warning"),
                "matches": sorted_matches,
                "allocation": allocation,
                "row_total": round(row_total, 2),
            }
        )
    totals = []
    for supplier in suppliers:
        amount = round(supplier_totals[supplier.id], 2)
        totals.append(
            {
                "supplier_id": supplier.id,
                "items_amount": amount,
                "min_order_amount": round(float(supplier.min_order_amount), 2),
                "min_order_passed": amount >= float(supplier.min_order_amount),
            }
        )
    return result_items, totals


def run_match(db: Session, order_text: str) -> dict:
    started = time.perf_counter()
    parsed_items, unparsed_lines = parse_order_text(order_text)
    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    prices = db.scalars(select(Price)).all()
    llm_input = _build_input_payload(parsed_items, suppliers, prices)
    degraded_mode = False
    degraded_reason = None
    try:
        model_result = _call_yandex_gpt(llm_input)
        model_result["items"] = _ensure_all_items_present(parsed_items, model_result.get("items", []))
        status = "ok"
    except HTTPException as exc:
        # MVP fail-safe: do not fail the whole matching run if LLM returns malformed JSON/network error.
        logger.exception("match_failed_using_fallback")
        degraded_mode = True
        degraded_reason = str(exc.detail)
        model_result = {
            "items": [
                {
                    "canonical_name": p["name"],
                    "quantity": p["quantity"],
                    "unit": p["unit"],
                    "matches": [],
                    "warning": "LLM недоступна, применен fallback",
                }
                for p in parsed_items
            ]
        }
        status = "degraded"
    model_result["items"] = _attach_db_fallback_matches(model_result["items"], prices, suppliers)
    items, supplier_totals = _compute_result(model_result, suppliers)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "match_request status=%s order_lines_total=%s order_lines_parsed=%s elapsed_ms=%s",
        status,
        len(order_text.splitlines()),
        len(parsed_items),
        elapsed_ms,
    )

    return {
        "currency": "RUB",
        "items": items,
        "supplier_totals": supplier_totals,
        "suppliers": [{"id": s.id, "name": s.name} for s in suppliers],
        "unparsed_lines": unparsed_lines,
        "degraded_mode": degraded_mode,
        "degraded_reason": degraded_reason,
        "elapsed_ms": elapsed_ms,
    }
