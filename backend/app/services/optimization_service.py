import logging
from dataclasses import dataclass

from sqlalchemy import delete, select
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
from app.services.procurement_batch_meta import apply_batch_status
from app.services.procurement_match_service import _match_row, match_ready_for_allocation

logger = logging.getLogger(__name__)

SUPPLIER_PENALTY_RUB = 500.0
OPTIMIZE_MODE_MIN_ORDER = "optimize_min_order"
OPTIMIZE_MODE_CHEAPEST = "cheapest_only"
OPTIMIZE_MODE_HYBRID = "hybrid_topup"
OPTIMIZE_MODES = {OPTIMIZE_MODE_MIN_ORDER, OPTIMIZE_MODE_CHEAPEST, OPTIMIZE_MODE_HYBRID}


@dataclass
class ProductOption:
    product_id: int
    product_name: str
    total_quantity: float
    unit: str
    options: list[dict]


def _optimizer_mode_label(mode: str) -> str:
    if mode == "milp":
        return "Оптимизация (MILP)"
    if mode == "greedy_fallback":
        return "Оптимизация (запасной алгоритм)"
    if mode == OPTIMIZE_MODE_MIN_ORDER:
        return "Оптимизация с учетом минимального заказа"
    if mode == OPTIMIZE_MODE_CHEAPEST:
        return "Мин. цена по позиции"
    if mode == OPTIMIZE_MODE_HYBRID:
        return "Гибрид: мин. цена + подсказка добора"
    if mode == "manual":
        return "Ручной override"
    return mode


def _line_quantity(line: DemandLine) -> float:
    if line.normalized_quantity is not None:
        return float(line.normalized_quantity)
    return float(line.quantity)


def _line_unit(line: DemandLine) -> str:
    return line.normalized_unit or line.unit


def _best_sku_for_pair(db: Session, product_id: int, supplier_id: int) -> SupplierSku | None:
    skus = db.scalars(
        select(SupplierSku)
        .where(
            SupplierSku.canonical_product_id == product_id,
            SupplierSku.supplier_id == supplier_id,
            SupplierSku.is_active == 1,
            SupplierSku.price_id.isnot(None),
        )
        .order_by(SupplierSku.is_preferred.desc(), SupplierSku.price.asc())
    ).all()
    return skus[0] if skus else None


def _build_product_options(db: Session, batch_id: int) -> tuple[list[ProductOption], list[dict]]:
    lines = db.scalars(
        select(DemandLine)
        .where(DemandLine.batch_id == batch_id)
        .order_by(DemandLine.id)
    ).all()
    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    skipped: list[dict] = []
    by_product: dict[int, dict] = {}

    for line in lines:
        row = _match_row(db, line)
        if not match_ready_for_allocation(row["match_status"]):
            skipped.append(
                {
                    "demand_line_id": line.id,
                    "raw_text": line.raw_text,
                    "match_status": row["match_status"],
                }
            )
            continue
        product_id = int(line.canonical_product_id)
        if product_id not in by_product:
            product = db.get(CanonicalProduct, product_id)
            by_product[product_id] = {
                "product_id": product_id,
                "product_name": product.name if product else "",
                "total_quantity": 0.0,
                "unit": _line_unit(line),
                "options": [],
            }
        entry = by_product[product_id]
        entry["total_quantity"] += _line_quantity(line)
        if _line_unit(line) != entry["unit"]:
            entry["unit"] = _line_unit(line)

    for product_id, entry in by_product.items():
        options = []
        for supplier in suppliers:
            sku = _best_sku_for_pair(db, product_id, supplier.id)
            if not sku:
                continue
            qty = entry["total_quantity"]
            options.append(
                {
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "supplier_sku_id": sku.id,
                    "unit_price": float(sku.price),
                    "line_cost": round(float(sku.price) * qty, 2),
                    "is_preferred": bool(sku.is_preferred),
                }
            )
        if not options:
            skipped.append(
                {
                    "demand_line_id": None,
                    "raw_text": entry["product_name"],
                    "match_status": "needs_sku",
                }
            )
            continue
        entry["options"] = options

    products = [
        ProductOption(
            product_id=entry["product_id"],
            product_name=entry["product_name"],
            total_quantity=round(entry["total_quantity"], 3),
            unit=entry["unit"],
            options=entry["options"],
        )
        for entry in by_product.values()
        if entry["options"]
    ]
    return products, skipped


def _solve_greedy(products: list[ProductOption], suppliers: list[Supplier]) -> dict[int, int]:
    """product_id -> supplier_id: cheapest per product."""
    assignment: dict[int, int] = {}
    for product in products:
        best = min(product.options, key=lambda o: (not o["is_preferred"], o["line_cost"]))
        assignment[product.product_id] = int(best["supplier_id"])
    return assignment


def _build_topup_suggestions(
    products: list[ProductOption], suppliers: list[Supplier], assignment: dict[int, int]
) -> list[dict]:
    supplier_names = {s.id: s.name for s in suppliers}
    min_orders = {s.id: float(s.min_order_amount or 0) for s in suppliers}

    assigned_cost_by_product: dict[int, float] = {}
    spend_by_supplier: dict[int, float] = {}
    for product in products:
        s_id = assignment.get(product.product_id)
        if not s_id:
            continue
        chosen = next((opt for opt in product.options if int(opt["supplier_id"]) == int(s_id)), None)
        if not chosen:
            continue
        line_cost = float(chosen["line_cost"])
        assigned_cost_by_product[product.product_id] = line_cost
        spend_by_supplier[s_id] = spend_by_supplier.get(s_id, 0.0) + line_cost

    suggestions: list[dict] = []
    for s_id, amount in spend_by_supplier.items():
        min_order = min_orders.get(s_id, 0.0)
        if min_order <= 0:
            continue
        deficit = round(max(0.0, min_order - amount), 2)
        if deficit <= 0:
            continue

        candidates: list[dict] = []
        for product in products:
            if assignment.get(product.product_id) == s_id:
                continue
            current_cost = assigned_cost_by_product.get(product.product_id)
            supplier_opt = next((opt for opt in product.options if int(opt["supplier_id"]) == int(s_id)), None)
            if current_cost is None or not supplier_opt:
                continue
            target_cost = float(supplier_opt["line_cost"])
            extra_cost = round(target_cost - current_cost, 2)
            candidates.append(
                {
                    "canonical_product_id": product.product_id,
                    "canonical_product_name": product.product_name,
                    "quantity": product.total_quantity,
                    "unit": product.unit,
                    "current_supplier_id": assignment.get(product.product_id),
                    "current_supplier_name": supplier_names.get(assignment.get(product.product_id), ""),
                    "target_supplier_id": s_id,
                    "target_supplier_name": supplier_names.get(s_id, ""),
                    "current_line_cost": round(current_cost, 2),
                    "target_line_cost": round(target_cost, 2),
                    "extra_cost": extra_cost,
                }
            )
        candidates.sort(key=lambda row: (row["extra_cost"], -row["target_line_cost"]))
        suggestions.append(
            {
                "supplier_id": s_id,
                "supplier_name": supplier_names.get(s_id, ""),
                "current_amount": round(amount, 2),
                "min_order_amount": round(min_order, 2),
                "deficit": deficit,
                "candidates": candidates[:8],
            }
        )
    suggestions.sort(key=lambda row: row["deficit"], reverse=True)
    return suggestions


def _solve_milp(products: list[ProductOption], suppliers: list[Supplier]) -> dict[int, int] | None:
    try:
        import pulp
    except ImportError:
        logger.warning("pulp_not_installed")
        return None

    supplier_ids = [s.id for s in suppliers]
    min_orders = {s.id: float(s.min_order_amount or 0) for s in suppliers}
    prob = pulp.LpProblem("procurement", pulp.LpMinimize)

    y_vars: dict[tuple[int, int], pulp.LpVariable] = {}
    z_vars: dict[int, pulp.LpVariable] = {s_id: pulp.LpVariable(f"z_{s_id}", cat=pulp.LpBinary) for s_id in supplier_ids}

    cost_terms = []
    for product in products:
        for opt in product.options:
            p_id = product.product_id
            s_id = int(opt["supplier_id"])
            var = pulp.LpVariable(f"y_{p_id}_{s_id}", cat=pulp.LpBinary)
            y_vars[(p_id, s_id)] = var
            cost_terms.append(opt["line_cost"] * var)

    prob += pulp.lpSum(cost_terms) + pulp.lpSum(SUPPLIER_PENALTY_RUB * z_vars[s_id] for s_id in supplier_ids)

    for product in products:
        p_id = product.product_id
        prob += pulp.lpSum(y_vars[(p_id, int(opt["supplier_id"]))] for opt in product.options) == 1

    for product in products:
        p_id = product.product_id
        for opt in product.options:
            s_id = int(opt["supplier_id"])
            prob += z_vars[s_id] >= y_vars[(p_id, s_id)]

    for s_id in supplier_ids:
        supplier_cost = []
        for product in products:
            p_id = product.product_id
            for opt in product.options:
                if int(opt["supplier_id"]) == s_id:
                    supplier_cost.append(opt["line_cost"] * y_vars[(p_id, s_id)])
        if supplier_cost:
            prob += pulp.lpSum(supplier_cost) >= min_orders[s_id] * z_vars[s_id]

    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if prob.status != pulp.LpStatusOptimal:
        return None

    assignment: dict[int, int] = {}
    for product in products:
        p_id = product.product_id
        chosen = None
        for opt in product.options:
            s_id = int(opt["supplier_id"])
            if pulp.value(y_vars[(p_id, s_id)]) and pulp.value(y_vars[(p_id, s_id)]) > 0.5:
                chosen = s_id
                break
        if chosen is None:
            return None
        assignment[p_id] = chosen
    return assignment


def _persist_allocations(
    db: Session,
    batch: ProcurementBatch,
    assignment: dict[int, int],
    source: str,
    optimizer_mode: str,
) -> None:
    db.execute(delete(Allocation).where(Allocation.batch_id == batch.id))
    db.execute(delete(SupplierOrderTotal).where(SupplierOrderTotal.batch_id == batch.id))

    lines = db.scalars(select(DemandLine).where(DemandLine.batch_id == batch.id)).all()
    supplier_amounts: dict[int, float] = {}

    for line in lines:
        if not line.canonical_product_id:
            continue
        product_id = int(line.canonical_product_id)
        supplier_id = assignment.get(product_id)
        if not supplier_id:
            continue
        sku = _best_sku_for_pair(db, product_id, supplier_id)
        if not sku:
            continue
        qty = _line_quantity(line)
        unit = _line_unit(line)
        unit_price = float(sku.price)
        amount = round(unit_price * qty, 2)
        db.add(
            Allocation(
                batch_id=batch.id,
                demand_line_id=line.id,
                supplier_id=supplier_id,
                supplier_sku_id=sku.id,
                quantity=qty,
                unit=unit,
                unit_price=unit_price,
                amount=amount,
                source=source,
            )
        )
        supplier_amounts[supplier_id] = supplier_amounts.get(supplier_id, 0.0) + amount

    suppliers = {s.id: s for s in db.scalars(select(Supplier)).all()}
    total = 0.0
    for supplier_id, amount in supplier_amounts.items():
        supplier = suppliers[supplier_id]
        min_order = float(supplier.min_order_amount or 0)
        passed = 1 if amount >= min_order else 0
        db.add(
            SupplierOrderTotal(
                batch_id=batch.id,
                supplier_id=supplier_id,
                amount=round(amount, 2),
                min_order_amount=min_order,
                min_order_passed=passed,
            )
        )
        total += amount

    batch.total_amount = round(total, 2)
    batch.optimizer_mode = optimizer_mode
    apply_batch_status(batch, "optimized")


def run_optimize(db: Session, batch_id: int, mode: str = OPTIMIZE_MODE_MIN_ORDER) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")
    if mode not in OPTIMIZE_MODES:
        raise ValueError("invalid_mode")

    products, skipped = _build_product_options(db, batch_id)
    if not products:
        raise ValueError("nothing_to_optimize")

    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    topup_suggestions: list[dict] = []
    assignment: dict[int, int] | None = None
    optimizer_mode = mode
    warning = None
    if mode == OPTIMIZE_MODE_MIN_ORDER:
        assignment = _solve_milp(products, suppliers)
        optimizer_mode = "milp"
        if assignment is None:
            assignment = _solve_greedy(products, suppliers)
            optimizer_mode = "greedy_fallback"
            warning = "MILP не нашёл решение — использован запасной алгоритм (мин. цена по позиции). Проверьте мин. заказы."
    elif mode == OPTIMIZE_MODE_CHEAPEST:
        assignment = _solve_greedy(products, suppliers)
        optimizer_mode = OPTIMIZE_MODE_CHEAPEST
    elif mode == OPTIMIZE_MODE_HYBRID:
        assignment = _solve_greedy(products, suppliers)
        optimizer_mode = OPTIMIZE_MODE_HYBRID
        topup_suggestions = _build_topup_suggestions(products, suppliers, assignment)
        if topup_suggestions:
            warning = "Показан базовый вариант по мин. цене и подсказки, какие позиции можно докинуть для выполнения минимального заказа."
    if assignment is None:
        raise ValueError("nothing_to_optimize")

    _persist_allocations(db, batch, assignment, "optimizer", optimizer_mode)
    db.commit()
    return get_allocation_state(db, batch_id, warning=warning, topup_suggestions=topup_suggestions)


def override_product_supplier(
    db: Session, batch_id: int, canonical_product_id: int, supplier_id: int
) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")
    if not db.get(Supplier, supplier_id):
        raise ValueError("supplier_not_found")
    if not _best_sku_for_pair(db, canonical_product_id, supplier_id):
        raise ValueError("sku_not_found")

    existing = db.scalars(select(Allocation).where(Allocation.batch_id == batch_id)).all()
    assignment: dict[int, int] = {}
    for alloc in existing:
        line = db.get(DemandLine, alloc.demand_line_id)
        if line and line.canonical_product_id:
            assignment[int(line.canonical_product_id)] = alloc.supplier_id
    if not assignment:
        products, _ = _build_product_options(db, batch_id)
        suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
        assignment = _solve_greedy(products, suppliers)
    assignment[canonical_product_id] = supplier_id

    _persist_allocations(db, batch, assignment, "manual_override", "manual")
    db.commit()
    return get_allocation_state(db, batch_id)


def get_allocation_state(
    db: Session, batch_id: int, warning: str | None = None, topup_suggestions: list[dict] | None = None
) -> dict:
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    totals = db.scalars(
        select(SupplierOrderTotal).where(SupplierOrderTotal.batch_id == batch_id)
    ).all()
    suppliers = {s.id: s for s in db.scalars(select(Supplier)).all()}
    supplier_rows = []
    for row in totals:
        supplier = suppliers.get(row.supplier_id)
        supplier_rows.append(
            {
                "supplier_id": row.supplier_id,
                "supplier_name": supplier.name if supplier else "",
                "amount": float(row.amount),
                "min_order_amount": float(row.min_order_amount),
                "min_order_passed": bool(row.min_order_passed),
            }
        )

    allocs = db.scalars(select(Allocation).where(Allocation.batch_id == batch_id)).all()
    by_product: dict[int, dict] = {}
    line_rows = []
    for alloc in allocs:
        line = db.get(DemandLine, alloc.demand_line_id)
        product = db.get(CanonicalProduct, line.canonical_product_id) if line else None
        supplier = suppliers.get(alloc.supplier_id)
        sku = db.get(SupplierSku, alloc.supplier_sku_id)
        line_rows.append(
            {
                "allocation_id": alloc.id,
                "demand_line_id": alloc.demand_line_id,
                "location_name": "",
                "department_name": "",
                "raw_text": line.raw_text if line else "",
                "canonical_product_id": line.canonical_product_id if line else None,
                "canonical_product_name": product.name if product else None,
                "supplier_id": alloc.supplier_id,
                "supplier_name": supplier.name if supplier else "",
                "name_in_price": sku.name_in_price if sku else "",
                "quantity": float(alloc.quantity),
                "unit": alloc.unit,
                "unit_price": float(alloc.unit_price),
                "amount": float(alloc.amount),
                "source": alloc.source,
            }
        )
        if line:
            loc = db.get(Location, line.location_id)
            dep = db.get(Department, line.department_id)
            line_rows[-1]["location_name"] = loc.name if loc else ""
            line_rows[-1]["department_name"] = dep.name if dep else ""
        if line and line.canonical_product_id:
            pid = int(line.canonical_product_id)
            if pid not in by_product:
                by_product[pid] = {
                    "canonical_product_id": pid,
                    "canonical_product_name": product.name if product else "",
                    "total_quantity": 0.0,
                    "unit": alloc.unit,
                    "supplier_id": alloc.supplier_id,
                    "supplier_name": supplier.name if supplier else "",
                    "line_cost": 0.0,
                }
            by_product[pid]["total_quantity"] += float(alloc.quantity)
            by_product[pid]["line_cost"] += float(alloc.amount)

    product_rows = []
    for entry in by_product.values():
        entry["total_quantity"] = round(entry["total_quantity"], 3)
        entry["line_cost"] = round(entry["line_cost"], 2)
        product_rows.append(entry)

    products, skipped = _build_product_options(db, batch_id)

    return {
        "batch_id": batch_id,
        "batch_status": batch.status,
        "optimizer_mode": batch.optimizer_mode,
        "mode_label": _optimizer_mode_label(batch.optimizer_mode or ""),
        "total_amount": float(batch.total_amount or 0),
        "warning": warning,
        "skipped_lines_count": len(skipped),
        "supplier_totals": supplier_rows,
        "product_assignments": product_rows,
        "line_allocations": line_rows,
        "available_suppliers": [
            {"supplier_id": s.id, "supplier_name": s.name} for s in suppliers.values()
        ],
        "optimizable_products": [
            {
                "canonical_product_id": p.product_id,
                "canonical_product_name": p.product_name,
                "total_quantity": p.total_quantity,
                "unit": p.unit,
                "options": p.options,
            }
            for p in products
        ],
        "topup_suggestions": topup_suggestions or [],
    }
