from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import CanonicalProduct, DemandLine, Department, Location, ProcurementBatch
from app.parsers.order_parser import parse_order_text
from app.services.procurement_batch_meta import apply_batch_status, sync_batch_display_title


def _find_canonical_id(db: Session, name: str) -> int | None:
    from app.services.procurement_match_service import resolve_canonical_product_id

    return resolve_canonical_product_id(db, name)


def batch_to_summary(db: Session, batch: ProcurementBatch) -> dict:
    lines = db.scalars(select(DemandLine).where(DemandLine.batch_id == batch.id)).all()
    slots: set[tuple[int, int]] = set()
    for line in lines:
        slots.add((line.location_id, line.department_id))

    active_locations = db.scalar(select(func.count(Location.id)).where(Location.is_active == 1)) or 0
    departments_count = db.scalar(select(func.count(Department.id))) or 2
    total_slots = int(active_locations) * int(departments_count)

    if lines:
        from app.services.procurement_match_service import match_counts_for_batch

        match_ok, match_problem = match_counts_for_batch(db, batch.id)
    else:
        match_ok, match_problem = 0, 0
    return {
        "id": batch.id,
        "title": batch.title,
        "plan_label": batch.plan_label,
        "responsible": batch.responsible,
        "status": batch.status,
        "created_at": batch.created_at.isoformat() if hasattr(batch.created_at, "isoformat") else str(batch.created_at),
        "created_by": batch.created_by,
        "demand_lines_count": len(lines),
        "filled_slots_count": len(slots),
        "total_slots_count": total_slots,
        "parse_ok_count": sum(1 for row in lines if row.parse_status == "ok"),
        "parse_problem_count": sum(1 for row in lines if row.parse_status != "ok"),
        "match_ok_count": match_ok,
        "match_problem_count": match_problem,
    }


def demand_line_to_out(db: Session, line: DemandLine) -> dict:
    location = db.get(Location, line.location_id)
    department = db.get(Department, line.department_id)
    product = db.get(CanonicalProduct, line.canonical_product_id) if line.canonical_product_id else None
    return {
        "id": line.id,
        "batch_id": line.batch_id,
        "location_id": line.location_id,
        "location_name": location.name if location else "",
        "department_id": line.department_id,
        "department_name": department.name if department else "",
        "canonical_product_id": line.canonical_product_id,
        "canonical_product_name": product.name if product else None,
        "raw_text": line.raw_text,
        "quantity": float(line.quantity),
        "unit": line.unit,
        "normalized_quantity": line.normalized_quantity,
        "normalized_unit": line.normalized_unit,
        "parse_status": line.parse_status,
        "line_notes": line.line_notes,
        "sort_order": int(line.sort_order),
    }


def save_demand_text(
    db: Session,
    batch_id: int,
    location_id: int,
    department_id: int,
    order_text: str,
) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")
    if not db.get(Location, location_id):
        raise ValueError("location_not_found")
    if not db.get(Department, department_id):
        raise ValueError("department_not_found")

    db.execute(
        delete(DemandLine).where(
            DemandLine.batch_id == batch_id,
            DemandLine.location_id == location_id,
            DemandLine.department_id == department_id,
        )
    )

    parsed_items, unparsed_lines = parse_order_text(order_text)
    sort_order = 0
    for item in parsed_items:
        canonical_id = _find_canonical_id(db, item["name"])
        status = "ok" if canonical_id else "needs_product"
        db.add(
            DemandLine(
                batch_id=batch_id,
                location_id=location_id,
                department_id=department_id,
                canonical_product_id=canonical_id,
                raw_text=f"{item['name']} {item['quantity']} {item['unit']}",
                quantity=float(item["quantity"]),
                unit=item["unit"],
                normalized_quantity=float(item["quantity"]),
                normalized_unit=item["unit"],
                parse_status=status,
                sort_order=sort_order,
            )
        )
        sort_order += 1

    for raw in unparsed_lines:
        db.add(
            DemandLine(
                batch_id=batch_id,
                location_id=location_id,
                department_id=department_id,
                raw_text=raw,
                quantity=0,
                unit="кг",
                parse_status="unparsed",
                sort_order=sort_order,
            )
        )
        sort_order += 1

    if batch.status == "draft" and (parsed_items or unparsed_lines):
        batch.status = "parsed"
    db.commit()
    return {"saved_lines": sort_order, "parsed_count": len(parsed_items), "unparsed_count": len(unparsed_lines)}


def parse_batch(db: Session, batch_id: int) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    lines = db.scalars(select(DemandLine).where(DemandLine.batch_id == batch_id)).all()
    ok_count = 0
    needs_product = 0
    unparsed_count = 0

    for line in lines:
        from app.parsers.order_parser import parse_single_line
        from app.services.procurement_match_service import _extract_demand_name, resolve_canonical_product_id

        item = parse_single_line(line.raw_text)
        if not item:
            demand_name = _extract_demand_name(line)
            canonical_id = resolve_canonical_product_id(db, demand_name)
            if canonical_id:
                line.canonical_product_id = canonical_id
                line.parse_status = "ok"
                ok_count += 1
            else:
                line.parse_status = "unparsed"
                line.quantity = 0
                unparsed_count += 1
            continue

        canonical_id = resolve_canonical_product_id(db, item["name"])
        line.quantity = float(item["quantity"])
        line.unit = item["unit"]
        line.normalized_quantity = float(item["quantity"])
        line.normalized_unit = item["unit"]
        line.canonical_product_id = canonical_id
        line.parse_status = "ok" if canonical_id else "needs_product"
        if canonical_id:
            ok_count += 1
        else:
            needs_product += 1

    apply_batch_status(batch, "parsed")
    db.commit()
    return {
        "total_lines": len(lines),
        "ok_count": ok_count,
        "needs_product_count": needs_product,
        "unparsed_count": unparsed_count,
    }
