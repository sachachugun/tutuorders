from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.auth import create_access_token, require_auth, verify_login
from app.db import get_db
from app.models import Price, Setting, Supplier
from app.parsers.order_parser import parse_order_text
from app.schemas import LoginRequest, MatchRequest, SettingsOut, SettingsUpdateRequest, SupplierUpdateRequest, SuppliersResponse
from app.services.export_service import build_export_xlsx
from app.services.match_service import run_match
from app.services.price_import_service import normalize_price_rows, parse_price_file, replace_supplier_prices

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
        count = db.scalar(select(func.count(Price.id)).where(Price.supplier_id == supplier.id)) or 0
        items.append(
            {
                "id": supplier.id,
                "name": supplier.name,
                "min_order_amount": round(float(supplier.min_order_amount), 2),
                "price_items_count": int(count),
                "last_price_upload_at": supplier.last_price_upload_at.isoformat() if supplier.last_price_upload_at else None,
            }
        )
    return {"items": items}


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
    replace_supplier_prices(db, supplier_id, normalized_rows)

    return {
        "supplier_id": supplier_id,
        "loaded_rows": len(source_rows),
        "saved_rows": len(normalized_rows),
        "skipped_rows": sum(stats.values()),
        "skips": stats,
        "last_price_upload_at": supplier.last_price_upload_at.isoformat() if supplier.last_price_upload_at else None,
        "filename": file.filename,
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
    count = db.scalar(select(func.count(Price.id)).where(Price.supplier_id == supplier.id)) or 0
    return {
        "id": supplier.id,
        "name": supplier.name,
        "min_order_amount": round(float(supplier.min_order_amount), 2),
        "price_items_count": int(count),
        "last_price_upload_at": supplier.last_price_upload_at.isoformat() if supplier.last_price_upload_at else None,
    }


@router.post("/export")
def export_xlsx(payload: dict, _: str = Depends(require_auth)):
    file_content = build_export_xlsx(payload)
    return Response(
        content=file_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=result.xlsx"},
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
