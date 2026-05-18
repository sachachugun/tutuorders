from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO

import openpyxl
import xlrd
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Price, Supplier

MAX_ROWS = 500
ALLOWED_UNITS = {"кг", "г", "л", "мл"}


def _to_float(raw_value: object) -> float:
    if raw_value is None:
        return 0
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    text = (
        str(raw_value)
        .strip()
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    return float(text) if text else 0


def _normalize_unit(raw_unit: object) -> str:
    unit = str(raw_unit or "").strip().lower()
    if unit == "гр":
        unit = "г"
    return unit if unit in ALLOWED_UNITS else "кг"


def parse_price_file(file_name: str, file_content: bytes, supplier_id: int) -> list[dict]:
    if not file_content:
        raise HTTPException(status_code=400, detail="Файл пустой. Загрузите прайс в формате .xls или .xlsx")
    ext = (file_name or "").lower()
    if ext.endswith(".xlsx"):
        return _parse_xlsx(file_content)
    if ext.endswith(".xls"):
        return _parse_xls(file_content)
    raise HTTPException(status_code=400, detail="Поддерживаются только .xls и .xlsx")


def _parse_xlsx(file_content: bytes) -> list[dict]:
    workbook = openpyxl.load_workbook(BytesIO(file_content), read_only=True, data_only=True)
    sheet = workbook.active
    header = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
    has_header = _looks_like_header(header)
    start_row = 2 if has_header else 1
    rows: list[dict] = []
    for index, row in enumerate(sheet.iter_rows(min_row=start_row, values_only=True), start=1):
        if index > MAX_ROWS:
            raise HTTPException(status_code=400, detail="Лимит прайса: не более 500 строк")
        rows.append(_extract_row(row, 0, 1, 2))
    if not rows:
        raise HTTPException(status_code=400, detail="Не найдено строк с данными в прайсе")
    return rows


def _parse_xls(file_content: bytes) -> list[dict]:
    workbook = xlrd.open_workbook(file_contents=file_content)
    sheet = workbook.sheet_by_index(0)
    header = sheet.row_values(0) if sheet.nrows > 0 else []
    has_header = _looks_like_header(header)
    start_row = 1 if has_header else 0
    rows: list[dict] = []
    for index, row_idx in enumerate(range(start_row, sheet.nrows), start=1):
        if index > MAX_ROWS:
            raise HTTPException(status_code=400, detail="Лимит прайса: не более 500 строк")
        row = sheet.row_values(row_idx)
        rows.append(_extract_row(row, 0, 1, 2))
    if not rows:
        raise HTTPException(status_code=400, detail="Не найдено строк с данными в прайсе")
    return rows


def _extract_row(row: object, col_name: int, col_unit: int, col_price: int) -> dict:
    name_in_price = str((row[col_name] if len(row) > col_name else "") or "").strip()
    raw_unit = str((row[col_unit] if len(row) > col_unit else "") or "").strip()
    unit = _normalize_unit(raw_unit)
    price = _to_float(row[col_price] if len(row) > col_price else 0)
    return {"name_in_price": name_in_price, "unit": unit, "raw_unit": raw_unit, "price": price}


def _looks_like_header(header: object) -> bool:
    normalized = [str(h or "").strip().lower() for h in (header or [])]
    if len(normalized) < 3:
        return False
    col_a = normalized[0]
    col_b = normalized[1]
    col_c = normalized[2]
    return (
        any(token in col_a for token in ("номенклат", "товар", "продукт", "наименование", "name"))
        and any(token in col_b for token in ("ед", "unit", "единиц"))
        and any(token in col_c for token in ("цена", "price", "стоим"))
    )


def normalize_price_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    dedup = defaultdict(lambda: None)
    stats = {"invalid_price": 0, "empty_name": 0, "duplicates_removed": 0, "section_rows": 0}
    for row in rows:
        name = (row.get("name_in_price") or "").strip()
        if not name:
            stats["empty_name"] += 1
            continue
        price = float(row.get("price", 0))
        if price <= 0:
            if _is_section_row(name, str(row.get("raw_unit", ""))):
                stats["section_rows"] += 1
            else:
                stats["invalid_price"] += 1
            continue

        existing = dedup[name]
        if existing is None or price < existing["price"]:
            if existing is not None:
                stats["duplicates_removed"] += 1
            dedup[name] = {"name_in_price": name, "unit": row.get("unit", "кг"), "price": round(price, 2)}
        else:
            stats["duplicates_removed"] += 1
    normalized = list(dedup.values())
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=(
                "Не найдено валидных позиций с ценой > 0. "
                "Проверьте, что в файле заполнены название, единица и цена."
            ),
        )
    return normalized, stats


def _is_section_row(name: str, raw_unit: str) -> bool:
    if raw_unit.strip():
        return False
    normalized = name.strip()
    if not normalized:
        return False
    # Typical section rows: short uppercase category labels like "ГРИБЫ", "ОВОЩИ".
    return len(normalized.split()) <= 3 and normalized.upper() == normalized


def replace_supplier_prices(db: Session, supplier_id: int, normalized_rows: list[dict]) -> None:
    db.execute(delete(Price).where(Price.supplier_id == supplier_id))
    for row in normalized_rows:
        db.add(
            Price(
                supplier_id=supplier_id,
                name_in_price=row["name_in_price"],
                unit=row["unit"],
                price=row["price"],
            )
        )
    supplier = db.get(Supplier, supplier_id)
    if supplier:
        supplier.last_price_upload_at = datetime.now(timezone.utc)
    db.commit()
