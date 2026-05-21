from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.auth import create_access_token, require_auth, verify_login
from app.db import get_db
from app.models import (
    CanonicalProduct,
    DemandLine,
    Department,
    Location,
    Price,
    ProductSpec,
    ProcurementBatch,
    Setting,
    Supplier,
    SupplierSku,
)
from app.parsers.order_parser import parse_order_text
from app.schemas import (
    CanonicalProductCreateRequest,
    CanonicalProductOut,
    CanonicalProductsResponse,
    CanonicalProductUpdateRequest,
    ProductDeleteImpactOut,
    ProductDeleteResultOut,
    DepartmentOut,
    DepartmentsResponse,
    LocationCreateRequest,
    LocationOut,
    LocationUpdateRequest,
    LocationsResponse,
    LoginRequest,
    MatchRequest,
    SettingsOut,
    SettingsUpdateRequest,
    SupplierCreateRequest,
    SupplierSkuCreateRequest,
    SupplierSkuOut,
    ProductSpecCreateRequest,
    ProductSpecOut,
    ProductSpecPreviewOut,
    AddProductFromDemandRequest,
    AddProductFromDemandResponse,
    ProductSkuSuggestRequest,
    ProductSkuSuggestResponse,
    DemandLineAssignProductRequest,
    DemandLineSuggestResponse,
    DemandLinesResponse,
    DemandMatchLineOut,
    DemandSaveRequest,
    ProcurementMatchResponse,
    ProductSpecPreviewRequest,
    ProductSpecsResponse,
    ProductSpecUpdateRequest,
    ProcurementBatchCreateRequest,
    ProcurementBatchOut,
    ProcurementOptimizeResponse,
    ProcurementSummaryResponse,
    ProductSupplierOverrideRequest,
    SupplierSkuUpdateRequest,
    SupplierOrderCommentUpdate,
    SupplierOrderLineOut,
    SupplierOrdersResponse,
    SupplierOut,
    SupplierUpdateRequest,
    SuppliersResponse,
)
from app.services.export_service import build_export_xlsx
from app.services.match_service import run_match
from app.services.price_import_service import normalize_price_rows, parse_price_file, replace_supplier_prices
from app.services.optimization_service import (
    get_allocation_state,
    override_product_supplier,
    run_optimize,
)
from app.services.procurement_match_service import (
    add_product_from_demand_gap,
    assign_demand_line_product,
    get_batch_match_state,
    run_batch_match,
    suggest_products_for_line,
)
from app.services.procurement_service import (
    batch_to_summary,
    demand_line_to_out,
    parse_batch,
    save_demand_text,
)
from app.services.procurement_summary_service import build_summary_export_xlsx, get_batch_summary
from app.services.sku_suggest_service import suggest_skus_for_product_name
from app.services.supplier_order_service import (
    build_procurement_batch_xlsx,
    build_supplier_orders,
    get_supplier_orders_state,
    update_order_line_comment,
)
from app.services.product_delete_service import delete_product_cascade, get_product_delete_impact
from app.services.spec_service import SCOPE_LABELS, format_scope_summary, resolve_spec_text

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/auth/login")
def login(payload: LoginRequest):
    if not verify_login(payload.username.strip(), payload.password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token, expires_at = create_access_token(payload.username.strip())
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at}


@router.get("/auth/me")
def auth_me(current_user: str = Depends(require_auth)):
    return {"username": current_user}


@router.get("/suppliers", response_model=SuppliersResponse)
def list_suppliers(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    items = []
    for supplier in suppliers:
        items.append(_supplier_to_out(db, supplier))
    return {"items": items}


def _supplier_to_out(db: Session, supplier: Supplier) -> dict:
    count = db.scalar(select(func.count(Price.id)).where(Price.supplier_id == supplier.id)) or 0
    unmatched = db.scalar(
        select(func.count(Price.id)).where(
            Price.supplier_id == supplier.id,
            ~exists(
                select(SupplierSku.id).where(
                    SupplierSku.supplier_id == Price.supplier_id,
                    SupplierSku.name_in_price == Price.name_in_price,
                    SupplierSku.is_active == 1,
                )
            ),
        )
    ) or 0
    return {
        "id": supplier.id,
        "name": supplier.name,
        "min_order_amount": round(float(supplier.min_order_amount), 2),
        "price_items_count": int(count),
        "unmatched_price_items_count": int(unmatched),
        "last_price_upload_at": supplier.last_price_upload_at.isoformat() if supplier.last_price_upload_at else None,
    }


@router.post("/suppliers", response_model=SupplierOut)
def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Укажите имя поставщика")
    existing = db.scalar(select(Supplier).where(Supplier.name == name))
    if existing:
        raise HTTPException(status_code=400, detail="Поставщик с таким именем уже существует")

    next_id = int(db.scalar(select(func.max(Supplier.id))) or 0) + 1
    supplier = Supplier(id=next_id, name=name, min_order_amount=float(payload.min_order_amount))
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return _supplier_to_out(db, supplier)


@router.get("/prices/format-help")
def prices_format_help(_: str = Depends(require_auth)):
    return {
        "common": [
            "Поддерживаются только .xls и .xlsx",
            "Один файл до 500 строк данных",
            "Формат колонок: A=название продукта, B=единица, C=цена",
            "Цена должна быть > 0",
            "Единицы: кг, г/гр, л, мл",
            "Первая строка может быть заголовком, это не обязательно",
        ]
    }


@router.post("/prices/upload")
async def upload_price(
    supplier_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    content = await file.read()
    source_rows = parse_price_file(file.filename or "", content, supplier_id)
    normalized_rows, stats = normalize_price_rows(source_rows)
    upload_stats = replace_supplier_prices(db, supplier_id, normalized_rows)

    return {
        "supplier_id": supplier_id,
        "loaded_rows": len(source_rows),
        "saved_rows": len(normalized_rows),
        "skipped_rows": sum(stats.values()),
        "skips": stats,
        "last_price_upload_at": supplier.last_price_upload_at.isoformat() if supplier.last_price_upload_at else None,
        "filename": file.filename,
        **upload_stats,
    }


@router.post("/match")
def match_order(payload: MatchRequest, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    return run_match(db, payload.order_text)


@router.post("/order/parse")
def parse_order(payload: MatchRequest, _: str = Depends(require_auth)):
    parsed_items, unparsed_lines = parse_order_text(payload.order_text)
    return {
        "parsed_items": parsed_items,
        "unparsed_lines": unparsed_lines,
        "parsed_count": len(parsed_items),
        "total_lines": len([line for line in payload.order_text.splitlines() if line.strip()]),
    }


@router.put("/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    supplier.name = payload.name.strip()
    supplier.min_order_amount = float(payload.min_order_amount)
    db.commit()
    db.refresh(supplier)
    return _supplier_to_out(db, supplier)


@router.post("/export")
def export_xlsx(payload: dict, _: str = Depends(require_auth)):
    file_content = build_export_xlsx(payload)
    return Response(
        content=file_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=result.xlsx"},
    )


def _location_to_out(location: Location) -> dict:
    return {
        "id": location.id,
        "code": location.code,
        "name": location.name,
        "sort_order": int(location.sort_order),
        "is_active": bool(location.is_active),
    }


def _normalize_location_code(code: str) -> str:
    normalized = code.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Укажите код локации")
    if not normalized.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Код локации: только латиница, цифры и _")
    return normalized


@router.get("/departments", response_model=DepartmentsResponse)
def list_departments(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    departments = db.scalars(select(Department).order_by(Department.id)).all()
    items = [DepartmentOut(id=d.id, code=d.code, name=d.name) for d in departments]
    return {"items": items}


@router.get("/locations", response_model=LocationsResponse)
def list_locations(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    locations = db.scalars(select(Location).order_by(Location.sort_order, Location.id)).all()
    return {"items": [_location_to_out(row) for row in locations]}


@router.post("/locations", response_model=LocationOut)
def create_location(
    payload: LocationCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    code = _normalize_location_code(payload.code)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Укажите название локации")

    existing = db.scalar(select(Location).where(Location.code == code))
    if existing:
        raise HTTPException(status_code=400, detail="Локация с таким кодом уже существует")

    location = Location(
        code=code,
        name=name,
        sort_order=int(payload.sort_order),
        is_active=1 if payload.is_active else 0,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return _location_to_out(location)


@router.put("/locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: int,
    payload: LocationUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Локация не найдена")

    code = _normalize_location_code(payload.code)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Укажите название локации")

    duplicate = db.scalar(
        select(Location).where(Location.code == code, Location.id != location_id)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Локация с таким кодом уже существует")

    location.code = code
    location.name = name
    location.sort_order = int(payload.sort_order)
    location.is_active = 1 if payload.is_active else 0
    db.commit()
    db.refresh(location)
    return _location_to_out(location)


@router.delete("/locations/{location_id}")
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    db.delete(location)
    db.commit()
    return {"ok": True}


ALLOWED_UNITS = {"кг", "г", "л", "мл"}
ALLOWED_MATCH_SOURCES = {"manual", "ai", "rule", "import"}


def _normalize_unit(unit: str) -> str:
    normalized = unit.strip().lower()
    if normalized == "гр":
        normalized = "г"
    if normalized not in ALLOWED_UNITS:
        raise HTTPException(status_code=400, detail="Единица должна быть одной из: кг, г, л, мл")
    return normalized


def _normalize_match_source(source: str) -> str:
    normalized = source.strip().lower() or "manual"
    if normalized not in ALLOWED_MATCH_SOURCES:
        raise HTTPException(status_code=400, detail="Некорректный source сопоставления")
    return normalized


def _sku_to_out(db: Session, sku: SupplierSku) -> dict:
    supplier = db.get(Supplier, sku.supplier_id)
    return {
        "id": sku.id,
        "supplier_id": sku.supplier_id,
        "supplier_name": supplier.name if supplier else f"#{sku.supplier_id}",
        "price_id": sku.price_id,
        "name_in_price": sku.name_in_price,
        "unit": sku.unit,
        "price": round(float(sku.price), 2),
        "is_preferred": bool(sku.is_preferred),
        "is_active": bool(sku.is_active),
        "match_source": sku.match_source,
        "match_score": sku.match_score,
    }


def _product_to_out(db: Session, product: CanonicalProduct) -> dict:
    skus = db.scalars(
        select(SupplierSku).where(SupplierSku.canonical_product_id == product.id).order_by(SupplierSku.supplier_id, SupplierSku.id)
    ).all()
    return {
        "id": product.id,
        "name": product.name,
        "default_unit": product.default_unit,
        "category": product.category,
        "notes": product.notes,
        "is_active": bool(product.is_active),
        "skus": [_sku_to_out(db, sku) for sku in skus],
    }


def _find_price_for_sku(db: Session, supplier_id: int, name_in_price: str) -> Price:
    price = db.scalar(
        select(Price).where(
            Price.supplier_id == supplier_id,
            Price.name_in_price == name_in_price,
        )
    )
    if not price:
        raise HTTPException(status_code=400, detail="В прайсе поставщика нет такой позиции")
    return price


@router.get("/products", response_model=CanonicalProductsResponse)
def list_products(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    products = db.scalars(select(CanonicalProduct).order_by(CanonicalProduct.name)).all()
    return {"items": [_product_to_out(db, row) for row in products]}


@router.post("/products/suggest-skus", response_model=ProductSkuSuggestResponse)
def suggest_product_skus(
    payload: ProductSkuSuggestRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    unit = (payload.unit or "").strip() or None
    if unit and unit not in {"кг", "г", "л", "мл"}:
        unit = None
    return suggest_skus_for_product_name(db, payload.name.strip(), unit)


@router.post("/products", response_model=CanonicalProductOut)
def create_product(
    payload: CanonicalProductCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Укажите название продукта")
    if db.scalar(select(CanonicalProduct).where(CanonicalProduct.name == name)):
        raise HTTPException(status_code=400, detail="Продукт с таким названием уже существует")
    product = CanonicalProduct(
        name=name,
        default_unit=_normalize_unit(payload.default_unit),
        category=(payload.category or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        is_active=1 if payload.is_active else 0,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_to_out(db, product)


@router.put("/products/{product_id}", response_model=CanonicalProductOut)
def update_product(
    product_id: int,
    payload: CanonicalProductUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Укажите название продукта")
    duplicate = db.scalar(
        select(CanonicalProduct).where(CanonicalProduct.name == name, CanonicalProduct.id != product_id)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Продукт с таким названием уже существует")
    product.name = name
    product.default_unit = _normalize_unit(payload.default_unit)
    product.category = (payload.category or "").strip() or None
    product.notes = (payload.notes or "").strip() or None
    product.is_active = 1 if payload.is_active else 0
    db.commit()
    db.refresh(product)
    return _product_to_out(db, product)


@router.get("/products/{product_id}/delete-impact", response_model=ProductDeleteImpactOut)
def product_delete_impact(product_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    return get_product_delete_impact(db, product_id)


@router.delete("/products/{product_id}", response_model=ProductDeleteResultOut)
def delete_product(product_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    deleted = delete_product_cascade(db, product_id)
    return {"ok": True, "deleted": deleted}


@router.post("/products/{product_id}/skus", response_model=SupplierSkuOut)
def create_product_sku(
    product_id: int,
    payload: SupplierSkuCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    name_in_price = payload.name_in_price.strip()
    if not name_in_price:
        raise HTTPException(status_code=400, detail="Укажите название из прайса")
    if db.scalar(
        select(SupplierSku).where(
            SupplierSku.canonical_product_id == product_id,
            SupplierSku.supplier_id == payload.supplier_id,
            SupplierSku.name_in_price == name_in_price,
        )
    ):
        raise HTTPException(status_code=400, detail="Такая привязка SKU уже существует")
    price_row = _find_price_for_sku(db, payload.supplier_id, name_in_price)
    sku = SupplierSku(
        canonical_product_id=product_id,
        supplier_id=payload.supplier_id,
        price_id=price_row.id,
        name_in_price=name_in_price,
        unit=price_row.unit,
        price=float(price_row.price),
        match_source=_normalize_match_source(payload.match_source),
        is_preferred=1 if payload.is_preferred else 0,
        is_active=1,
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return _sku_to_out(db, sku)


@router.put("/products/{product_id}/skus/{sku_id}", response_model=SupplierSkuOut)
def update_product_sku(
    product_id: int,
    sku_id: int,
    payload: SupplierSkuUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    sku = db.get(SupplierSku, sku_id)
    if not sku or sku.canonical_product_id != product_id:
        raise HTTPException(status_code=404, detail="SKU не найден")
    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    name_in_price = payload.name_in_price.strip()
    if not name_in_price:
        raise HTTPException(status_code=400, detail="Укажите название из прайса")
    duplicate = db.scalar(
        select(SupplierSku).where(
            SupplierSku.canonical_product_id == product_id,
            SupplierSku.supplier_id == payload.supplier_id,
            SupplierSku.name_in_price == name_in_price,
            SupplierSku.id != sku_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Такая привязка SKU уже существует")
    price_row = _find_price_for_sku(db, payload.supplier_id, name_in_price)
    sku.supplier_id = payload.supplier_id
    sku.name_in_price = name_in_price
    sku.price_id = price_row.id
    sku.unit = price_row.unit
    sku.price = float(price_row.price)
    sku.is_preferred = 1 if payload.is_preferred else 0
    sku.is_active = 1 if payload.is_active else 0
    db.commit()
    db.refresh(sku)
    return _sku_to_out(db, sku)


@router.delete("/products/{product_id}/skus/{sku_id}")
def delete_product_sku(
    product_id: int,
    sku_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    sku = db.get(SupplierSku, sku_id)
    if not sku or sku.canonical_product_id != product_id:
        raise HTTPException(status_code=404, detail="SKU не найден")
    db.delete(sku)
    db.commit()
    return {"ok": True}


@router.get("/prices/unmatched")
def list_unmatched_prices(
    supplier_id: int | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    conditions = [
        ~exists(
            select(SupplierSku.id).where(
                SupplierSku.supplier_id == Price.supplier_id,
                SupplierSku.name_in_price == Price.name_in_price,
                SupplierSku.is_active == 1,
            )
        )
    ]
    if supplier_id is not None:
        conditions.append(Price.supplier_id == supplier_id)
    rows = db.execute(
        select(
            Price.id,
            Price.supplier_id,
            Supplier.name,
            Price.name_in_price,
            Price.unit,
            Price.price,
        )
        .join(Supplier, Supplier.id == Price.supplier_id)
        .where(and_(*conditions))
        .order_by(Supplier.name, Price.name_in_price)
    ).all()
    return {
        "items": [
            {
                "price_id": row[0],
                "supplier_id": row[1],
                "supplier_name": row[2],
                "name_in_price": row[3],
                "unit": row[4],
                "price": float(row[5]),
            }
            for row in rows
        ]
    }


ALLOWED_SCOPE_TYPES = {
    "global",
    "department",
    "location",
    "location_department",
    "supplier",
    "supplier_department",
    "supplier_location",
}


def _normalize_scope_payload(
    scope_type: str,
    location_id: int | None,
    department_id: int | None,
    supplier_id: int | None,
) -> tuple[str, int | None, int | None, int | None]:
    scope = scope_type.strip().lower()
    if scope not in ALLOWED_SCOPE_TYPES:
        raise HTTPException(status_code=400, detail="Некорректный тип области правила")

    loc = department = supplier = None
    if scope in {"location", "location_department", "supplier_location"}:
        if not location_id:
            raise HTTPException(status_code=400, detail="Укажите локацию для выбранной области")
        loc = location_id
    if scope in {"department", "location_department", "supplier_department"}:
        if not department_id:
            raise HTTPException(status_code=400, detail="Укажите отдел для выбранной области")
        department = department_id
    if scope in {"supplier", "supplier_department", "supplier_location"}:
        if not supplier_id:
            raise HTTPException(status_code=400, detail="Укажите поставщика для выбранной области")
        supplier = supplier_id
    return scope, loc, department, supplier


def _spec_to_out(db: Session, spec: ProductSpec) -> dict:
    created = spec.created_at.isoformat() if hasattr(spec.created_at, "isoformat") else str(spec.created_at or "")
    return {
        "id": spec.id,
        "canonical_product_id": spec.canonical_product_id,
        "version": int(spec.version),
        "scope_type": spec.scope_type,
        "scope_label": SCOPE_LABELS.get(spec.scope_type, spec.scope_type),
        "scope_summary": format_scope_summary(spec, db),
        "scope_location_id": spec.scope_location_id,
        "scope_department_id": spec.scope_department_id,
        "scope_supplier_id": spec.scope_supplier_id,
        "spec_text": spec.spec_text,
        "append_to_supplier_order": bool(spec.append_to_supplier_order),
        "valid_from": spec.valid_from,
        "valid_to": spec.valid_to,
        "is_active": bool(spec.is_active),
        "created_at": created or None,
    }


@router.get("/products/{product_id}/specs", response_model=ProductSpecsResponse)
def list_product_specs(product_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    specs = db.scalars(
        select(ProductSpec)
        .where(ProductSpec.canonical_product_id == product_id)
        .order_by(ProductSpec.scope_type, ProductSpec.id)
    ).all()
    return {"items": [_spec_to_out(db, row) for row in specs]}


@router.post("/products/{product_id}/specs", response_model=ProductSpecOut)
def create_product_spec(
    product_id: int,
    payload: ProductSpecCreateRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    text = payload.spec_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Укажите текст спецификации")
    scope, loc, department, supplier = _normalize_scope_payload(
        payload.scope_type,
        payload.scope_location_id,
        payload.scope_department_id,
        payload.scope_supplier_id,
    )
    spec = ProductSpec(
        canonical_product_id=product_id,
        scope_type=scope,
        scope_location_id=loc,
        scope_department_id=department,
        scope_supplier_id=supplier,
        spec_text=text,
        append_to_supplier_order=1 if payload.append_to_supplier_order else 0,
        valid_from=(payload.valid_from or "").strip() or None,
        valid_to=(payload.valid_to or "").strip() or None,
        is_active=1 if payload.is_active else 0,
        created_by=current_user,
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)
    return _spec_to_out(db, spec)


@router.put("/products/{product_id}/specs/{spec_id}", response_model=ProductSpecOut)
def update_product_spec(
    product_id: int,
    spec_id: int,
    payload: ProductSpecUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    spec = db.get(ProductSpec, spec_id)
    if not spec or spec.canonical_product_id != product_id:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    text = payload.spec_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Укажите текст спецификации")
    scope, loc, department, supplier = _normalize_scope_payload(
        payload.scope_type,
        payload.scope_location_id,
        payload.scope_department_id,
        payload.scope_supplier_id,
    )
    if text != spec.spec_text:
        spec.version = int(spec.version) + 1
    spec.scope_type = scope
    spec.scope_location_id = loc
    spec.scope_department_id = department
    spec.scope_supplier_id = supplier
    spec.spec_text = text
    spec.append_to_supplier_order = 1 if payload.append_to_supplier_order else 0
    spec.valid_from = (payload.valid_from or "").strip() or None
    spec.valid_to = (payload.valid_to or "").strip() or None
    spec.is_active = 1 if payload.is_active else 0
    db.commit()
    db.refresh(spec)
    return _spec_to_out(db, spec)


@router.delete("/products/{product_id}/specs/{spec_id}")
def delete_product_spec(
    product_id: int,
    spec_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    spec = db.get(ProductSpec, spec_id)
    if not spec or spec.canonical_product_id != product_id:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    db.delete(spec)
    db.commit()
    return {"ok": True}


@router.post("/products/{product_id}/specs/preview", response_model=ProductSpecPreviewOut)
def preview_product_spec(
    product_id: int,
    payload: ProductSpecPreviewRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    result = resolve_spec_text(
        db,
        product_id,
        supplier_id=payload.supplier_id,
        location_id=payload.location_id,
        department_id=payload.department_id,
    )
    return result


@router.post("/procurement/batches", response_model=ProcurementBatchOut)
def create_procurement_batch(
    payload: ProcurementBatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
):
    from app.services.procurement_batch_meta import RESPONSIBLE_OPTIONS, init_new_batch

    plan_label = payload.plan_label.strip()
    if not plan_label:
        raise HTTPException(status_code=400, detail="Укажите название плана")
    responsible = (payload.responsible or "").strip() or None
    if responsible and responsible not in RESPONSIBLE_OPTIONS:
        raise HTTPException(status_code=400, detail="Ответственный: Женя или Андрей")
    batch = ProcurementBatch(created_by=current_user)
    init_new_batch(batch, plan_label, responsible)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch_to_summary(db, batch)


@router.get("/procurement/batches")
def list_procurement_batches(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        batches = db.scalars(select(ProcurementBatch).order_by(ProcurementBatch.id.desc())).all()
        return {"items": [batch_to_summary(db, row) for row in batches]}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Таблицы плана закупки не найдены. На сервере выполните миграции: "
                "cd /opt/tutuorders/backend && source .venv/bin/activate && "
                "python -c \"from app.db_migrate import run_pending_migrations; run_pending_migrations()\""
            ),
        ) from exc


@router.get("/procurement/batches/{batch_id}", response_model=ProcurementBatchOut)
def get_procurement_batch(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="План закупки не найден")
    return batch_to_summary(db, batch)


@router.get("/procurement/batches/{batch_id}/demand", response_model=DemandLinesResponse)
def list_batch_demand(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="План закупки не найден")
    lines = db.scalars(
        select(DemandLine)
        .where(DemandLine.batch_id == batch_id)
        .order_by(DemandLine.location_id, DemandLine.department_id, DemandLine.sort_order, DemandLine.id)
    ).all()
    return {"items": [demand_line_to_out(db, row) for row in lines]}


@router.post("/procurement/batches/{batch_id}/demand")
def save_batch_demand(
    batch_id: int,
    payload: DemandSaveRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        result = save_demand_text(
            db,
            batch_id,
            payload.location_id,
            payload.department_id,
            payload.order_text,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code in {"location_not_found", "department_not_found"}:
            raise HTTPException(status_code=404, detail="Локация или отдел не найдены") from exc
        raise
    return result


@router.post("/procurement/batches/{batch_id}/parse")
def parse_procurement_batch(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return parse_batch(db, batch_id)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        raise


@router.get("/procurement/batches/{batch_id}/match", response_model=ProcurementMatchResponse)
def get_procurement_batch_match(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return get_batch_match_state(db, batch_id)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        raise


@router.post("/procurement/batches/{batch_id}/match", response_model=ProcurementMatchResponse)
def run_procurement_batch_match(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return run_batch_match(db, batch_id)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        raise


@router.patch(
    "/procurement/batches/{batch_id}/demand/{line_id}",
    response_model=DemandMatchLineOut,
)
def assign_procurement_demand_product(
    batch_id: int,
    line_id: int,
    payload: DemandLineAssignProductRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        return assign_demand_line_product(db, batch_id, line_id, payload.canonical_product_id)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "line_not_found":
            raise HTTPException(status_code=404, detail="Строка спроса не найдена") from exc
        if code == "product_not_found":
            raise HTTPException(status_code=404, detail="Продукт не найден") from exc
        raise


@router.post(
    "/procurement/batches/{batch_id}/demand/{line_id}/suggest",
    response_model=DemandLineSuggestResponse,
)
def suggest_procurement_demand_product(
    batch_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        return suggest_products_for_line(db, batch_id, line_id)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "line_not_found":
            raise HTTPException(status_code=404, detail="Строка спроса не найдена") from exc
        raise


@router.post(
    "/procurement/batches/{batch_id}/dictionary/add",
    response_model=AddProductFromDemandResponse,
)
def add_dictionary_product_from_demand(
    batch_id: int,
    payload: AddProductFromDemandRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        sku_links = [{"supplier_id": row.supplier_id, "name_in_price": row.name_in_price} for row in payload.sku_links]
        return add_product_from_demand_gap(db, batch_id, payload.demand_name, payload.default_unit, sku_links)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "empty_name":
            raise HTTPException(status_code=400, detail="Укажите название продукта") from exc
        raise


@router.get("/procurement/batches/{batch_id}/allocations", response_model=ProcurementOptimizeResponse)
def get_procurement_allocations(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return get_allocation_state(db, batch_id)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        raise


@router.post("/procurement/batches/{batch_id}/optimize", response_model=ProcurementOptimizeResponse)
def optimize_procurement_batch(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return run_optimize(db, batch_id)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "nothing_to_optimize":
            raise HTTPException(
                status_code=400,
                detail="Нет строк для оптимизации — завершите проверку (все строки OK + SKU)",
            ) from exc
        raise


@router.patch(
    "/procurement/batches/{batch_id}/products/{canonical_product_id}/supplier",
    response_model=ProcurementOptimizeResponse,
)
def override_procurement_product_supplier(
    batch_id: int,
    canonical_product_id: int,
    payload: ProductSupplierOverrideRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        return override_product_supplier(db, batch_id, canonical_product_id, payload.supplier_id)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "supplier_not_found":
            raise HTTPException(status_code=404, detail="Поставщик не найден") from exc
        if code == "sku_not_found":
            raise HTTPException(status_code=400, detail="У поставщика нет SKU для этого продукта") from exc
        raise


@router.post("/procurement/batches/{batch_id}/build-orders", response_model=SupplierOrdersResponse)
def build_procurement_orders(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return build_supplier_orders(db, batch_id)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "no_allocations":
            raise HTTPException(status_code=400, detail="Сначала выполните распределение по поставщикам") from exc
        raise


@router.get("/procurement/batches/{batch_id}/orders", response_model=SupplierOrdersResponse)
def get_procurement_orders(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    try:
        return get_supplier_orders_state(db, batch_id)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        raise


@router.patch(
    "/procurement/batches/{batch_id}/orders/{line_id}",
    response_model=SupplierOrderLineOut,
)
def update_procurement_order_line(
    batch_id: int,
    line_id: int,
    payload: SupplierOrderCommentUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        return update_order_line_comment(db, batch_id, line_id, payload.line_comment)
    except ValueError as exc:
        code = str(exc)
        if code == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        if code == "line_not_found":
            raise HTTPException(status_code=404, detail="Строка заказа не найдена") from exc
        raise


@router.get("/procurement/batches/{batch_id}/summary", response_model=ProcurementSummaryResponse)
def get_procurement_summary(
    batch_id: int,
    location_id: int | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        return get_batch_summary(db, batch_id, location_id, department_id)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="План закупки не найден") from exc
        raise


@router.get("/procurement/batches/{batch_id}/summary/export")
def export_procurement_summary(
    batch_id: int,
    location_id: int | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    if not db.get(ProcurementBatch, batch_id):
        raise HTTPException(status_code=404, detail="План закупки не найден")
    try:
        content = build_summary_export_xlsx(db, batch_id, location_id, department_id)
    except ValueError as exc:
        code = str(exc)
        if code == "nothing_to_export":
            raise HTTPException(status_code=400, detail="Нет данных для сводки — выполните распределение") from exc
        raise
    suffix = ""
    if location_id:
        suffix += f"_loc{location_id}"
    if department_id:
        suffix += f"_dep{department_id}"
    filename = f"svodka_{batch_id}{suffix}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/procurement/batches/{batch_id}/export")
def export_procurement_batch(batch_id: int, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    batch = db.get(ProcurementBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="План закупки не найден")
    try:
        content = build_procurement_batch_xlsx(db, batch_id)
    except ValueError as exc:
        code = str(exc)
        if code == "orders_not_built":
            raise HTTPException(status_code=400, detail="Сначала соберите заказы поставщикам") from exc
        raise
    filename = f"zakupka_{batch_id}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    folder_id = db.get(Setting, "folder_id")
    model_name = db.get(Setting, "model_name")
    return {
        "folder_id": folder_id.value if folder_id else "",
        "model_name": model_name.value if model_name else settings.yandex_model_name,
        "api_key_configured": bool(settings.yandex_api_key),
    }


@router.put("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdateRequest, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    for key, value in (("folder_id", payload.folder_id), ("model_name", payload.model_name)):
        entry = db.get(Setting, key)
        if entry:
            entry.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
    return {
        "folder_id": payload.folder_id,
        "model_name": payload.model_name,
        "api_key_configured": bool(settings.yandex_api_key),
    }
