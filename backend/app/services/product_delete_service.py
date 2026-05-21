from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import (
    Allocation,
    CanonicalProduct,
    DemandLine,
    ProcurementBatch,
    ProductSpec,
    SupplierOrderLine,
    SupplierOrderTotal,
    SupplierSku,
)


def _allocation_rows(db: Session, product_id: int, line_ids: list[int], sku_ids: list[int]) -> list[tuple[int, int]]:
    if not line_ids and not sku_ids:
        return []
    clauses = []
    if line_ids:
        clauses.append(Allocation.demand_line_id.in_(line_ids))
    if sku_ids:
        clauses.append(Allocation.supplier_sku_id.in_(sku_ids))
    return db.execute(select(Allocation.id, Allocation.batch_id).where(or_(*clauses))).all()


def get_product_delete_impact(db: Session, product_id: int) -> dict:
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    sku_ids = list(
        db.scalars(select(SupplierSku.id).where(SupplierSku.canonical_product_id == product_id)).all()
    )
    spec_count = int(
        db.scalar(select(func.count()).select_from(ProductSpec).where(ProductSpec.canonical_product_id == product_id))
        or 0
    )
    line_ids = list(
        db.scalars(select(DemandLine.id).where(DemandLine.canonical_product_id == product_id)).all()
    )
    demand_line_count = len(line_ids)

    alloc_rows = _allocation_rows(db, product_id, line_ids, sku_ids)
    allocation_ids = [row[0] for row in alloc_rows]
    batch_ids = sorted({row[1] for row in alloc_rows})

    order_line_count = 0
    if allocation_ids:
        order_line_count = int(
            db.scalar(
                select(func.count())
                .select_from(SupplierOrderLine)
                .where(SupplierOrderLine.allocation_id.in_(allocation_ids))
            )
            or 0
        )

    batch_titles: list[str] = []
    if batch_ids:
        batches = db.scalars(select(ProcurementBatch).where(ProcurementBatch.id.in_(batch_ids))).all()
        batch_titles = [batch.title for batch in batches]

    return {
        "product_id": product.id,
        "product_name": product.name,
        "sku_count": len(sku_ids),
        "spec_count": spec_count,
        "demand_line_count": demand_line_count,
        "allocation_count": len(allocation_ids),
        "order_line_count": order_line_count,
        "batch_titles": batch_titles,
    }


def delete_product_cascade(db: Session, product_id: int) -> dict:
    impact = get_product_delete_impact(db, product_id)
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    line_ids = list(
        db.scalars(select(DemandLine.id).where(DemandLine.canonical_product_id == product_id)).all()
    )
    sku_ids = list(
        db.scalars(select(SupplierSku.id).where(SupplierSku.canonical_product_id == product_id)).all()
    )
    alloc_rows = _allocation_rows(db, product_id, line_ids, sku_ids)
    allocation_ids = [row[0] for row in alloc_rows]
    batch_ids = sorted({row[1] for row in alloc_rows})

    if allocation_ids:
        db.execute(delete(SupplierOrderLine).where(SupplierOrderLine.allocation_id.in_(allocation_ids)))
        db.execute(delete(Allocation).where(Allocation.id.in_(allocation_ids)))
    if batch_ids:
        db.execute(delete(SupplierOrderTotal).where(SupplierOrderTotal.batch_id.in_(batch_ids)))

    db.execute(
        update(DemandLine)
        .where(DemandLine.canonical_product_id == product_id)
        .values(canonical_product_id=None)
    )
    db.delete(product)
    db.commit()
    return impact
