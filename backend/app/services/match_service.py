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
UNIT_GROUP = {
    "кг": "mass",
    "г": "mass",
    "л": "volume",
    "мл": "volume",
}


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
    parsed = json.loads(candidate)
    if isinstance(parsed, list):
        return {"items": parsed}
    if isinstance(parsed, dict):
        return parsed
    raise json.JSONDecodeError("Top-level JSON must be object or array", candidate, 0)


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


def _tokenize_name(value: str) -> set[str]:
    tokens = re.findall(r"[a-zа-я0-9]+", _normalize_name(value))
    return {token for token in tokens if len(token) >= 2}


_RU_STEM_SUFFIXES = (
    "ами",
    "ями",
    "ого",
    "ому",
    "ием",
    "иях",
    "иям",
    "ов",
    "ев",
    "ей",
    "ий",
    "ый",
    "ой",
    "ая",
    "ые",
    "ии",
    "и",
    "ы",
    "а",
    "о",
    "е",
    "я",
    "ь",
)


def _stem_ru_token(token: str) -> str:
    """Light Russian plural/suffix normalization (яблоко ≈ яблоки)."""
    word = (token or "").lower()
    if len(word) < 5:
        return word
    # One ending only — avoids «яблоки» → «ябл» via «ки»
    if word[-1] in "оеыиаяь":
        root = word[:-1]
        if len(root) >= 4:
            return root
    for suffix in _RU_STEM_SUFFIXES:
        if len(suffix) >= 2 and word.endswith(suffix):
            root = word[: -len(suffix)]
            if len(root) >= 4:
                return root
    return word


def _stem_token_set(tokens: set[str]) -> set[str]:
    return {_stem_ru_token(token) for token in tokens}


def _units_compatible(order_unit: str, candidate_unit: str) -> bool:
    order_group = UNIT_GROUP.get((order_unit or "").strip().lower())
    candidate_group = UNIT_GROUP.get((candidate_unit or "").strip().lower())
    if not order_group or not candidate_group:
        return True
    return order_group == candidate_group


def _name_match_score(needle: str, hay: str) -> float:
    if not needle or not hay:
        return 0.0
    if needle == hay:
        return 1.0
    if needle in hay or hay in needle:
        return 0.95
    needle_tokens = _tokenize_name(needle)
    hay_tokens = _tokenize_name(hay)
    if not needle_tokens or not hay_tokens:
        return 0.0

    intersection = needle_tokens & hay_tokens
    union = needle_tokens | hay_tokens
    token_score = len(intersection) / len(union) if intersection else 0.0

    needle_stems = _stem_token_set(needle_tokens)
    hay_stems = _stem_token_set(hay_tokens)
    stem_intersection = needle_stems & hay_stems
    if stem_intersection:
        stem_union = needle_stems | hay_stems
        stem_score = len(stem_intersection) / len(stem_union)
        token_score = max(token_score, stem_score)
        # «Яблоки» vs «яблоко гренни» — один канонический корень в длинном спросе
        if len(hay_stems) == 1 and hay_stems <= needle_stems:
            token_score = max(token_score, 0.92)

    return token_score


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
        order_unit = str(item.get("unit", ""))
        if not needle:
            continue

        fallback_matches = []
        for supplier in suppliers:
            best_price: Price | None = None
            best_score = 0.0
            for candidate in by_supplier.get(supplier.id, []):
                if not _units_compatible(order_unit, candidate.unit):
                    continue
                hay = _normalize_name(candidate.name_in_price)
                if not hay:
                    continue
                score = _name_match_score(needle, hay)
                if score < 0.6:
                    continue
                if (
                    best_price is None
                    or score > best_score
                    or (score == best_score and float(candidate.price) < float(best_price.price))
                ):
                    best_price = candidate
                    best_score = score
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


def _repair_json_via_model(payload: dict, invalid_text: str) -> dict:
    body = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_model_name}/latest",
        "completionOptions": {"temperature": 0.0, "maxTokens": 4000},
        "messages": [
            {
                "role": "system",
                "text": (
                    "Преобразуй ответ в строго валидный JSON-объект формата "
                    '{"items":[{"canonical_name":"string","quantity":0,"unit":"кг|г|л|мл","matches":[{"supplier_id":0,'
                    '"name_in_price":"string","price":0,"note":null}],"warning":null}]}. '
                    "Верни только JSON без markdown и комментариев."
                ),
            },
            {
                "role": "user",
                "text": json.dumps(
                    {
                        "input_payload": payload,
                        "invalid_model_text": invalid_text,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}
    with httpx.Client(timeout=settings.yandex_timeout_seconds) as client:
        response = client.post(YANDEX_URL, headers=headers, json=body)
    if response.status_code >= 400:
        body_excerpt = _safe_error_text(response.text)
        logger.error("yandex_gpt_repair_failed status=%s body=%s", response.status_code, body_excerpt)
        raise HTTPException(status_code=502, detail=f"YandexGPT repair {response.status_code}: {body_excerpt}")
    data = response.json()
    try:
        text = data["result"]["alternatives"][0]["message"]["text"]
    except (KeyError, IndexError, TypeError):
        logger.error("yandex_gpt_repair_unexpected_response body=%s", _safe_error_text(json.dumps(data, ensure_ascii=False)))
        raise HTTPException(status_code=502, detail="YandexGPT repair returned unexpected response format")
    return _loads_model_json(text)


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
            try:
                return _repair_json_via_model(payload, retry_text if "retry_text" in locals() else raw_text)
            except (HTTPException, httpx.HTTPError, json.JSONDecodeError):
                raise HTTPException(status_code=502, detail="YandexGPT returned invalid JSON after repair attempt")


def _build_item_comment(
    item_name: str,
    item_unit: str,
    matches: list[dict],
    allocation: list[dict],
    suppliers: list[Supplier],
    prices: list[Price],
) -> str:
    if not matches:
        return "Не найдено совпадений в прайсах поставщиков"
    supplier_name_by_id = {s.id: s.name for s in suppliers}
    needle = _normalize_name(item_name)
    order_unit = (item_unit or "").strip().lower()

    alternatives_by_supplier: dict[int, list[dict]] = {}
    for supplier in suppliers:
        alternatives_by_supplier[supplier.id] = []
    for price in prices:
        if order_unit and not _units_compatible(order_unit, price.unit):
            continue
        hay = _normalize_name(price.name_in_price)
        if not hay:
            continue
        if _name_match_score(needle, hay) >= 0.6:
            alternatives_by_supplier.setdefault(price.supplier_id, []).append(
                {
                    "name_in_price": price.name_in_price,
                    "price": round(float(price.price), 2),
                }
            )
    for supplier_id in alternatives_by_supplier:
        alternatives_by_supplier[supplier_id] = sorted(
            alternatives_by_supplier[supplier_id], key=lambda x: float(x["price"])
        )

    selected = [a for a in allocation if float(a.get("quantity", 0)) > 0]
    selected_parts: list[str] = []
    for chosen in selected:
        supplier_id = int(chosen["supplier_id"])
        supplier_alternatives = alternatives_by_supplier.get(supplier_id, [])
        if supplier_alternatives:
            top = supplier_alternatives[0]
            selected_parts.append(
                f"{supplier_name_by_id.get(supplier_id, f'S{supplier_id}')}: "
                f"{top.get('name_in_price', '—')} ({float(top.get('price', 0)):.2f} RUB)"
            )
    alternatives: list[str] = []
    for supplier in suppliers:
        supplier_id = supplier.id
        supplier_alternatives = alternatives_by_supplier.get(supplier_id, [])
        if supplier_alternatives:
            alt_text = ", ".join(
                f"{m.get('name_in_price', '—')} ({float(m.get('price', 0)):.2f})" for m in supplier_alternatives
            )
        else:
            alt_text = "нет"
        alternatives.append(f"{supplier_name_by_id.get(supplier_id, f'S{supplier_id}')}: {alt_text}")
    selected_text = "; ".join(selected_parts) if selected_parts else "не выбран"
    alternatives_text = " | ".join(alternatives) if alternatives else "нет"
    return f"Выбранный товар: {selected_text}. Альтернативы: {alternatives_text}"


def _compute_result(model_result: dict, suppliers: list[Supplier], prices: list[Price]) -> tuple[list[dict], list[dict]]:
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
                "warning": item.get("warning") or ("Не найдено в прайсах поставщиков" if not sorted_matches else None),
                "matches": sorted_matches,
                "allocation": allocation,
                "row_total": round(row_total, 2),
                "comment": _build_item_comment(
                    item.get("canonical_name", ""),
                    item.get("unit", ""),
                    sorted_matches,
                    allocation,
                    suppliers,
                    prices,
                ),
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
    items, supplier_totals = _compute_result(model_result, suppliers, prices)
    not_found_in_suppliers = [
        {"name": item["canonical_name"], "quantity": item["quantity"], "unit": item["unit"]}
        for item in items
        if not item.get("matches")
    ]
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
        "not_found_in_suppliers": not_found_in_suppliers,
        "degraded_mode": degraded_mode,
        "degraded_reason": degraded_reason,
        "elapsed_ms": elapsed_ms,
    }
