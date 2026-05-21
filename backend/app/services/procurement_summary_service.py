from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Allocation,
    CanonicalProduct,
    DemandLine,
    Department,
    Location,
    ProcurementBatch,
    Supplier,
    SupplierOrderTotal,
    SupplierSku,
)
from app.services.export_service import build_export_xlsx


def _sku_prices_by_supplier(db: Session, product_id: int, supplier_ids: list[int]) -> list[dict]:
    rows = []
    for supplier_id in supplier_ids:
        sku = db.scalar(
            select(SupplierSku)
            .where(
                SupplierSku.canonical_product_id == product_id,
                SupplierSku.supplier_id == supplier_id,
                SupplierSku.is_active == 1,
            )
            .order_by(SupplierSku.is_preferred.desc(), SupplierSku.price.asc())
        )
        if sku:
            supplier = db.get(Supplier, supplier_id)
            rows.append(
                {
                    "supplier_id": supplier_id,
                    "price": float(sku.price),
                    "name_in_price": sku.name_in_price,
                    "note": supplier.name if supplier else None,
                }
            )
    return rows


def get_batch_summary(
    db: Session,
    batch_id: int,
    location_id: int | None = None,
    department_id: int | None = None,
) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    supplier_ids = [s.id for s in suppliers]
    supplier_list = [{"id": s.id, "name": s.name, "min_order_amount": float(s.min_order_amount or 0)} for s in suppliers]

    lines = db.scalars(
        select(DemandLine)
        .where(DemandLine.batch_id == batch_id)
        .order_by(DemandLine.location_id, DemandLine.department_id, DemandLine.sort_order, DemandLine.id)
    ).all()

    if location_id is not None:
        lines = [line for line in lines if line.location_id == location_id]
    if department_id is not None:
        lines = [line for line in lines if line.department_id == department_id]

    alloc_by_line_id = {
        row.demand_line_id: row
        for row in db.scalars(select(Allocation).where(Allocation.batch_id == batch_id)).all()
    }

    problems: list[dict] = []
    by_product: dict[int | str, dict] = {}

    for line in lines:
        loc = db.get(Location, line.location_id)
        dep = db.get(Department, line.department_id)
        alloc = alloc_by_line_id.get(line.id)

        if not line.canonical_product_id:
            problems.append(
                {
                    "demand_line_id": line.id,
                    "raw_text": line.raw_text,
                    "location_name": loc.name if loc else "",
                    "department_name": dep.name if dep else "",
                    "reason": "needs_product",
                }
            )
            continue

        if not alloc:
            product = db.get(CanonicalProduct, line.canonical_product_id)
            problems.append(
                {
                    "demand_line_id": line.id,
                    "raw_text": line.raw_text,
                    "canonical_product_name": product.name if product else "",
                    "location_name": loc.name if loc else "",
                    "department_name": dep.name if dep else "",
                    "reason": "no_allocation",
                }
            )
            continue

        pid = int(line.canonical_product_id)
        product = db.get(CanonicalProduct, pid)
        key = pid
        if key not in by_product:
            by_product[key] = {
                "canonical_product_id": pid,
                "canonical_name": product.name if product else "",
                "unit": line.unit,
                "quantity": 0.0,
                "matches": _sku_prices_by_supplier(db, pid, supplier_ids),
                "allocation": [],
                "_alloc_qty": defaultdict(float),
                "_alloc_amount": defaultdict(float),
                "_alloc_price": {},
                "row_total": 0.0,
                "comment": "",
                "has_allocation": True,
            }

        entry = by_product[key]
        qty = float(line.normalized_quantity if line.normalized_quantity is not None else line.quantity)
        entry["quantity"] += qty
        sid = int(alloc.supplier_id)
        entry["_alloc_qty"][sid] += float(alloc.quantity)
        entry["_alloc_amount"][sid] += float(alloc.amount)
        entry["_alloc_price"][sid] = float(alloc.unit_price)
        entry["row_total"] += float(alloc.amount)

    items: list[dict] = []
    for entry in by_product.values():
        allocation = []
        for sid in supplier_ids:
            qty = entry["_alloc_qty"].get(sid, 0.0)
            if qty > 0:
                allocation.append(
                    {
                        "supplier_id": sid,
                        "quantity": round(qty, 3),
                        "amount": round(entry["_alloc_amount"][sid], 2),
                        "price": entry["_alloc_price"].get(sid, 0.0),
                    }
                )
        del entry["_alloc_qty"]
        del entry["_alloc_amount"]
        del entry["_alloc_price"]
        entry["quantity"] = round(entry["quantity"], 3)
        entry["row_total"] = round(entry["row_total"], 2)
        entry["allocation"] = allocation
        items.append(entry)

    items.sort(key=lambda row: row["canonical_name"].lower())

    supplier_totals_map: dict[int, float] = defaultdict(float)
    for item in items:
        for alloc in item["allocation"]:
            supplier_totals_map[int(alloc["supplier_id"])] += float(alloc["amount"])

    order_totals = {
        row.supplier_id: row
        for row in db.scalars(select(SupplierOrderTotal).where(SupplierOrderTotal.batch_id == batch_id)).all()
    }

    supplier_totals = []
    for supplier in suppliers:
        amount = round(supplier_totals_map.get(supplier.id, 0.0), 2)
        min_order = float(supplier.min_order_amount or 0)
        global_row = order_totals.get(supplier.id)
        supplier_totals.append(
            {
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "amount": amount,
                "min_order_amount": min_order,
                "min_order_passed": amount >= min_order if amount > 0 else (global_row.min_order_passed if global_row else True),
                "used_in_filter": amount > 0,
            }
        )

    loc_filter = db.get(Location, location_id) if location_id else None
    dep_filter = db.get(Department, department_id) if department_id else None

    return {
        "batch_id": batch_id,
        "batch_title": batch.title,
        "batch_status": batch.status,
        "total_amount": round(sum(item["row_total"] for item in items), 2),
        "currency": "RUB",
        "location_id": location_id,
        "location_name": loc_filter.name if loc_filter else None,
        "department_id": department_id,
        "department_name": dep_filter.name if dep_filter else None,
        "suppliers": supplier_list,
        "supplier_ids": supplier_ids,
        "supplier_totals": supplier_totals,
        "items": items,
        "problems": problems,
        "items_count": len(items),
        "problems_count": len(problems),
    }


def build_summary_export_xlsx(
    db: Session,
    batch_id: int,
    location_id: int | None = None,
    department_id: int | None = None,
) -> bytes:
    summary = get_batch_summary(db, batch_id, location_id, department_id)
    if not summary["items"] and not summary["problems"]:
        raise ValueError("nothing_to_export")

    supplier_names = {str(s["id"]): s["name"] for s in summary["suppliers"]}
    meta_rows = [
        ["Сводка закупки (внутренняя)"],
        [f"План: {summary['batch_title']}"],
        [f"Фильтр: {_filter_label(summary)}"],
        [f"Итого по фильтру: {summary['total_amount']} {summary['currency']}"],
    ]
    payload = {
        "sheet_title": "svodka",
        "meta_rows": meta_rows,
        "currency": summary["currency"],
        "items": summary["items"],
        "supplier_ids": summary["supplier_ids"],
        "supplier_names": supplier_names,
    }
    return build_export_xlsx(payload)


def _filter_label(summary: dict) -> str:
    parts = []
    if summary.get("location_name"):
        parts.append(summary["location_name"])
    if summary.get("department_name"):
        parts.append(summary["department_name"])
    return " · ".join(parts) if parts else "Все локации и отделы"
