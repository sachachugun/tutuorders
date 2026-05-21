from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    min_order_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    last_price_upload_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_prices_price_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    name_in_price: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"
    __table_args__ = (
        CheckConstraint("default_unit IN ('кг', 'г', 'л', 'мл')", name="ck_canonical_products_default_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    default_unit: Mapped[str] = mapped_column(String(10), nullable=False, default="кг")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SupplierSku(Base):
    __tablename__ = "supplier_skus"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_supplier_skus_price_positive"),
        CheckConstraint("unit IN ('кг', 'г', 'л', 'мл')", name="ck_supplier_skus_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_product_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    price_id: Mapped[int | None] = mapped_column(ForeignKey("prices.id", ondelete="SET NULL"), nullable=True)
    name_in_price: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    match_source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_preferred: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProductSpec(Base):
    __tablename__ = "product_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_product_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, default="global")
    scope_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    scope_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    scope_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=True)
    spec_text: Mapped[str] = mapped_column(Text, nullable=False)
    append_to_supplier_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    valid_from: Mapped[str | None] = mapped_column(String(20), nullable=True)
    valid_to: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ProcurementBatch(Base):
    __tablename__ = "procurement_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    optimizer_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="milp")
    optimizer_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)


class DemandLine(Base):
    __tablename__ = "demand_lines"
    __table_args__ = (
        CheckConstraint("unit IN ('кг', 'г', 'л', 'мл')", name="ck_demand_lines_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    canonical_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_products.id"), nullable=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    normalized_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    line_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("unit IN ('кг', 'г', 'л', 'мл')", name="ck_allocations_unit"),
        CheckConstraint("source IN ('optimizer', 'manual_override')", name="ck_allocations_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    demand_line_id: Mapped[int] = mapped_column(
        ForeignKey("demand_lines.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    supplier_sku_id: Mapped[int] = mapped_column(ForeignKey("supplier_skus.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="optimizer")


class SupplierOrderTotal(Base):
    __tablename__ = "supplier_order_totals"

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_batches.id", ondelete="CASCADE"), primary_key=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), primary_key=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    min_order_amount: Mapped[float] = mapped_column(Float, nullable=False)
    min_order_passed: Mapped[int] = mapped_column(Integer, nullable=False)


class SupplierOrderLine(Base):
    __tablename__ = "supplier_order_lines"
    __table_args__ = (
        CheckConstraint("unit IN ('кг', 'г', 'л', 'мл')", name="ck_supplier_order_lines_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    allocation_id: Mapped[int] = mapped_column(
        ForeignKey("allocations.id", ondelete="CASCADE"), nullable=False
    )
    supplier_product_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    spec_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
