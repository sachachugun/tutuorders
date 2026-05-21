import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CanonicalProduct, DemandLine, ProcurementBatch, Supplier, SupplierSku
from app.services.sku_suggest_service import find_price_row
from app.parsers.order_parser import parse_order_text, parse_single_line
from app.services.match_service import _name_match_score, _normalize_name
from app.services.procurement_ai_match_service import ai_resolve_demand_to_products, yandex_configured
from app.services.procurement_batch_meta import apply_batch_status
from app.services.procurement_service import demand_line_to_out

AUTO_MATCH_MIN_SCORE = 0.82
AUTO_MATCH_CLEAR_SCORE = 0.95
SUGGEST_DISPLAY_MIN_SCORE = 0.35
SUGGEST_LIMIT = 6


def resolve_canonical_product_id(db: Session, name: str) -> int | None:
    """Exact name first, then fuzzy (same logic as «Подсказать», with auto-pick)."""
    needle = _normalize_name(name)
    if not needle:
        return None

    exact = db.scalar(
        select(CanonicalProduct.id).where(
            func.lower(CanonicalProduct.name) == needle,
            CanonicalProduct.is_active == 1,
        )
    )
    if exact:
        return int(exact)

    products = db.scalars(select(CanonicalProduct).where(CanonicalProduct.is_active == 1)).all()
    scored: list[tuple[float, CanonicalProduct]] = []
    for product in products:
        score = _name_match_score(needle, _normalize_name(product.name))
        if score >= AUTO_MATCH_MIN_SCORE:
            scored.append((score, product))
    if not scored:
        return None

    scored.sort(key=lambda row: row[0], reverse=True)
    best_score, best = scored[0]
    if best_score >= AUTO_MATCH_CLEAR_SCORE:
        return best.id
    if len(scored) > 1 and scored[1][0] >= best_score - 0.05:
        return None
    return best.id


def _extract_demand_name(line: DemandLine) -> str:
    item = parse_single_line(line.raw_text)
    if item:
        return str(item["name"])
    parsed_items, _ = parse_order_text(line.raw_text)
    if parsed_items:
        return str(parsed_items[0]["name"])
    text = line.raw_text.strip()
    text = re.sub(
        r"\s*\(\s*\d+(?:[.,]\d+)?\s*(?:кг|kg|г|гр|л|l|мл|ml)\s*\)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(r"\s+\d+(?:[.,]\d+)?\s*(?:кг|kg|г|гр|л|l|мл|ml)\s*$", "", text, flags=re.IGNORECASE).strip()
    return text or line.raw_text.strip()


def _supplier_sku_coverage(db: Session, canonical_product_id: int | None) -> list[dict]:
    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    if not canonical_product_id:
        return [
            {
                "supplier_id": s.id,
                "supplier_name": s.name,
                "has_sku": False,
                "sku_id": None,
                "name_in_price": None,
                "price": None,
            }
            for s in suppliers
        ]

    skus = db.scalars(
        select(SupplierSku).where(SupplierSku.canonical_product_id == canonical_product_id)
    ).all()
    by_supplier = {sku.supplier_id: sku for sku in skus}
    rows = []
    for supplier in suppliers:
        sku = by_supplier.get(supplier.id)
        sku_linked = sku is not None
        price_available = sku is not None and sku.price_id is not None
        rows.append(
            {
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "has_sku": price_available,
                "sku_linked": sku_linked,
                "missing_in_price": sku_linked and not price_available,
                "sku_id": sku.id if sku_linked else None,
                "name_in_price": sku.name_in_price if sku else None,
                "price": float(sku.price) if price_available else None,
            }
        )
    return rows


def _compute_match_status(line: DemandLine, supplier_skus: list[dict]) -> str:
    if line.parse_status == "unparsed":
        return "unparsed"
    if not line.canonical_product_id:
        return "needs_product"
    with_price = [row for row in supplier_skus if row["has_sku"]]
    if not with_price:
        return "needs_sku"
    if len(with_price) < len(supplier_skus):
        return "partial_sku"
    return "ok"


def match_ready_for_allocation(match_status: str) -> bool:
    return match_status in ("ok", "partial_sku")


def _suggest_products_for_name(db: Session, name: str, limit: int = SUGGEST_LIMIT) -> list[dict]:
    needle = _normalize_name(name)
    if not needle:
        return []
    products = db.scalars(select(CanonicalProduct).where(CanonicalProduct.is_active == 1)).all()
    scored: list[tuple[float, CanonicalProduct]] = []
    for product in products:
        score = _name_match_score(needle, _normalize_name(product.name))
        if score >= SUGGEST_DISPLAY_MIN_SCORE:
            scored.append((score, product))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [
        {
            "product_id": product.id,
            "name": product.name,
            "default_unit": product.default_unit,
            "score": round(score, 3),
        }
        for score, product in scored[:limit]
    ]


def _build_dictionary_gaps(items: list[dict]) -> list[dict]:
    """Unique demand names with no canonical match and no fuzzy suggestions in dictionary."""
    by_key: dict[str, dict] = {}
    for row in items:
        if row["match_status"] not in ("needs_product", "unparsed"):
            continue
        if row.get("suggestions"):
            continue
        demand_name = (row.get("demand_name") or "").strip()
        if not demand_name:
            continue
        key = _normalize_name(demand_name)
        if key not in by_key:
            by_key[key] = {
                "demand_name": demand_name,
                "default_unit": row.get("unit") or "кг",
                "line_count": 0,
                "line_ids": [],
            }
        by_key[key]["line_count"] += 1
        by_key[key]["line_ids"].append(row["id"])
        if row.get("unit"):
            by_key[key]["default_unit"] = row["unit"]
    gaps = list(by_key.values())
    gaps.sort(key=lambda row: (-row["line_count"], row["demand_name"].lower()))
    return gaps


def _match_row(db: Session, line: DemandLine) -> dict:
    base = demand_line_to_out(db, line)
    supplier_skus = _supplier_sku_coverage(db, line.canonical_product_id)
    match_status = _compute_match_status(line, supplier_skus)
    demand_name = _extract_demand_name(line)
    suggestions: list[dict] = []
    if match_status in ("needs_product", "unparsed"):
        suggestions = _suggest_products_for_name(db, demand_name)
    return {
        **base,
        "match_status": match_status,
        "demand_name": demand_name,
        "supplier_skus": supplier_skus,
        "suggestions": suggestions,
    }


def get_batch_match_state(db: Session, batch_id: int) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    lines = db.scalars(
        select(DemandLine)
        .where(DemandLine.batch_id == batch_id)
        .order_by(DemandLine.location_id, DemandLine.department_id, DemandLine.sort_order, DemandLine.id)
    ).all()
    items = [_match_row(db, line) for line in lines]
    ok_count = sum(1 for row in items if match_ready_for_allocation(row["match_status"]))
    problem_count = len(items) - ok_count
    products_missing_price = count_products_missing_price(db)

    return {
        "batch_id": batch_id,
        "batch_status": batch.status,
        "total_lines": len(items),
        "ok_count": ok_count,
        "problem_count": problem_count,
        "needs_product_count": sum(1 for row in items if row["match_status"] == "needs_product"),
        "needs_sku_count": sum(1 for row in items if row["match_status"] == "needs_sku"),
        "partial_sku_count": sum(1 for row in items if row["match_status"] == "partial_sku"),
        "unparsed_count": sum(1 for row in items if row["match_status"] == "unparsed"),
        "dictionary_gaps": _build_dictionary_gaps(items),
        "items": items,
        "match_mode": "local",
        "ai_assigned_count": 0,
        "ai_available": yandex_configured(),
        "products_missing_price_count": products_missing_price,
    }


def run_batch_match(db: Session, batch_id: int) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    lines = db.scalars(select(DemandLine).where(DemandLine.batch_id == batch_id)).all()
    ai_assigned_count = 0
    match_mode = "local"

    for line in lines:
        demand_name = _extract_demand_name(line)
        canonical_id = resolve_canonical_product_id(db, demand_name)
        line.canonical_product_id = canonical_id
        if canonical_id:
            line.parse_status = "ok"
        elif line.parse_status != "unparsed":
            line.parse_status = "needs_product"

    unresolved_by_name: dict[str, list[DemandLine]] = {}
    for line in lines:
        if line.canonical_product_id:
            continue
        demand_name = _extract_demand_name(line)
        if demand_name:
            unresolved_by_name.setdefault(demand_name, []).append(line)

    if unresolved_by_name and yandex_configured():
        ai_map = ai_resolve_demand_to_products(db, list(unresolved_by_name.keys()))
        if ai_map:
            match_mode = "local+ai"
            for demand_name, affected_lines in unresolved_by_name.items():
                product_id = ai_map.get(demand_name.strip().lower())
                if not product_id:
                    continue
                for line in affected_lines:
                    if line.canonical_product_id:
                        continue
                    line.canonical_product_id = product_id
                    line.parse_status = "ok"
                    ai_assigned_count += 1

    state = get_batch_match_state(db, batch_id)
    if state["total_lines"] and state["problem_count"] == 0:
        apply_batch_status(batch, "matched")
    elif state["total_lines"]:
        apply_batch_status(batch, "parsed")
    else:
        from app.services.procurement_batch_meta import sync_batch_display_title

        sync_batch_display_title(batch)
    db.commit()
    state["batch_status"] = batch.status
    state["match_mode"] = match_mode
    state["ai_assigned_count"] = ai_assigned_count
    state["ai_available"] = yandex_configured()
    return state


def assign_demand_line_product(db: Session, batch_id: int, line_id: int, canonical_product_id: int) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")
    line = db.get(DemandLine, line_id)
    if not line or line.batch_id != batch_id:
        raise ValueError("line_not_found")

    product = db.get(CanonicalProduct, canonical_product_id)
    if not product or not product.is_active:
        raise ValueError("product_not_found")

    line.canonical_product_id = canonical_product_id
    if line.parse_status == "unparsed":
        line.parse_status = "ok"
    db.commit()
    return _match_row(db, line)


def suggest_products_for_line(db: Session, batch_id: int, line_id: int, limit: int = 8) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")
    line = db.get(DemandLine, line_id)
    if not line or line.batch_id != batch_id:
        raise ValueError("line_not_found")

    demand_name = _extract_demand_name(line)
    suggestions = _suggest_products_for_name(db, demand_name, limit=limit)
    return {"line_id": line_id, "demand_name": demand_name, "suggestions": suggestions}


def _attach_skus_to_product(
    db: Session,
    product_id: int,
    sku_links: list[dict],
) -> int:
    created = 0
    for link in sku_links:
        supplier_id = int(link["supplier_id"])
        name_in_price = str(link.get("name_in_price") or "").strip()
        if not name_in_price:
            continue
        exists = db.scalar(
            select(SupplierSku).where(
                SupplierSku.canonical_product_id == product_id,
                SupplierSku.supplier_id == supplier_id,
                SupplierSku.name_in_price == name_in_price,
            )
        )
        if exists:
            continue
        price_row = find_price_row(db, supplier_id, name_in_price)
        if not price_row:
            continue
        db.add(
            SupplierSku(
                canonical_product_id=product_id,
                supplier_id=supplier_id,
                price_id=price_row.id,
                name_in_price=name_in_price,
                unit=price_row.unit,
                price=float(price_row.price),
                match_source="manual",
                is_preferred=0,
                is_active=1,
            )
        )
        created += 1
    return created


def add_product_from_demand_gap(
    db: Session,
    batch_id: int,
    demand_name: str,
    default_unit: str = "кг",
    sku_links: list[dict] | None = None,
) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    name = demand_name.strip()
    if not name:
        raise ValueError("empty_name")

    unit = default_unit.strip() if default_unit else "кг"
    if unit not in {"кг", "г", "л", "мл"}:
        unit = "кг"

    existing = db.scalar(
        select(CanonicalProduct.id).where(func.lower(CanonicalProduct.name) == name.lower())
    )
    if existing:
        product_id = int(existing)
        product = db.get(CanonicalProduct, product_id)
    else:
        product = CanonicalProduct(name=name, default_unit=unit, is_active=1)
        db.add(product)
        db.flush()

    skus_created = _attach_skus_to_product(db, product.id, sku_links or [])

    target_key = _normalize_name(name)
    lines = db.scalars(select(DemandLine).where(DemandLine.batch_id == batch_id)).all()
    assigned = 0
    for line in lines:
        if _normalize_name(_extract_demand_name(line)) != target_key:
            continue
        line.canonical_product_id = product.id
        line.parse_status = "ok"
        assigned += 1

    db.commit()
    state = get_batch_match_state(db, batch_id)
    return {
        "product_id": product.id,
        "product_name": product.name,
        "assigned_lines": assigned,
        "skus_created": skus_created,
        "match": state,
    }


def count_products_missing_price(db: Session) -> int:
    rows = db.scalars(
        select(SupplierSku.canonical_product_id).where(SupplierSku.price_id.is_(None))
    ).all()
    return len(set(rows))


def match_counts_for_batch(db: Session, batch_id: int) -> tuple[int, int]:
    state = get_batch_match_state(db, batch_id)
    return state["ok_count"], state["problem_count"]
