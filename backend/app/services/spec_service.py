from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProductSpec

SCOPE_PRIORITY = (
    "supplier_location",
    "supplier_department",
    "supplier",
    "location_department",
    "location",
    "department",
    "global",
)

SCOPE_LABELS = {
    "global": "Глобально",
    "department": "Отдел",
    "location": "Локация",
    "location_department": "Локация + отдел",
    "supplier": "Поставщик",
    "supplier_department": "Поставщик + отдел",
    "supplier_location": "Поставщик + локация",
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    return date.fromisoformat(text)


def _is_spec_valid_today(spec: ProductSpec, on_date: date | None = None) -> bool:
    if not spec.is_active:
        return False
    today = on_date or date.today()
    valid_from = _parse_date(spec.valid_from)
    valid_to = _parse_date(spec.valid_to)
    if valid_from and today < valid_from:
        return False
    if valid_to and today > valid_to:
        return False
    return True


def _spec_matches_context(
    spec: ProductSpec,
    *,
    supplier_id: int | None,
    location_id: int | None,
    department_id: int | None,
) -> bool:
    scope = spec.scope_type
    if scope == "global":
        return True
    if scope == "department":
        return department_id is not None and spec.scope_department_id == department_id
    if scope == "location":
        return location_id is not None and spec.scope_location_id == location_id
    if scope == "location_department":
        return (
            location_id is not None
            and department_id is not None
            and spec.scope_location_id == location_id
            and spec.scope_department_id == department_id
        )
    if scope == "supplier":
        return supplier_id is not None and spec.scope_supplier_id == supplier_id
    if scope == "supplier_department":
        return (
            supplier_id is not None
            and department_id is not None
            and spec.scope_supplier_id == supplier_id
            and spec.scope_department_id == department_id
        )
    if scope == "supplier_location":
        return (
            supplier_id is not None
            and location_id is not None
            and spec.scope_supplier_id == supplier_id
            and spec.scope_location_id == location_id
        )
    return False


def resolve_spec_text(
    db: Session,
    product_id: int,
    *,
    supplier_id: int | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
    on_date: date | None = None,
) -> dict:
    specs = db.scalars(
        select(ProductSpec).where(ProductSpec.canonical_product_id == product_id)
    ).all()
    candidates: list[ProductSpec] = []
    for spec in specs:
        if not _is_spec_valid_today(spec, on_date):
            continue
        if not spec.append_to_supplier_order:
            continue
        if not _spec_matches_context(
            spec,
            supplier_id=supplier_id,
            location_id=location_id,
            department_id=department_id,
        ):
            continue
        candidates.append(spec)

    priority_index = {scope: idx for idx, scope in enumerate(SCOPE_PRIORITY)}
    candidates.sort(key=lambda row: priority_index.get(row.scope_type, 99))

    if not candidates:
        return {
            "spec_text": "",
            "matched_spec_id": None,
            "matched_scope_type": None,
            "matched_scope_label": None,
        }

    winner = candidates[0]
    return {
        "spec_text": (winner.spec_text or "").strip(),
        "matched_spec_id": winner.id,
        "matched_scope_type": winner.scope_type,
        "matched_scope_label": SCOPE_LABELS.get(winner.scope_type, winner.scope_type),
    }


def format_scope_summary(spec: ProductSpec, db: Session) -> str:
    from app.models import Department, Location, Supplier

    if spec.scope_type == "global":
        return "Глобально"
    parts: list[str] = []
    if spec.scope_location_id:
        loc = db.get(Location, spec.scope_location_id)
        parts.append(loc.name if loc else f"loc#{spec.scope_location_id}")
    if spec.scope_department_id:
        dep = db.get(Department, spec.scope_department_id)
        parts.append(dep.name if dep else f"dep#{spec.scope_department_id}")
    if spec.scope_supplier_id:
        sup = db.get(Supplier, spec.scope_supplier_id)
        parts.append(sup.name if sup else f"sup#{spec.scope_supplier_id}")
    return " · ".join(parts) if parts else SCOPE_LABELS.get(spec.scope_type, spec.scope_type)
