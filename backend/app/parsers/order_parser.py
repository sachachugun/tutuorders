import re

LINE_RE = re.compile(r"^\s*(?P<name>.+?)\s+(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>кг|г|гр|л|мл)\s*$", re.IGNORECASE)

UNIT_MAP = {
    "кг": "кг",
    "г": "г",
    "гр": "г",
    "л": "л",
    "мл": "мл",
}


def parse_order_text(order_text: str) -> tuple[list[dict], list[str]]:
    parsed: list[dict] = []
    unparsed: list[str] = []

    for raw_line in order_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = LINE_RE.match(line)
        if not match:
            unparsed.append(line)
            continue
        quantity = float(match.group("quantity").replace(",", "."))
        clean_name = _clean_name(match.group("name"))
        unit = UNIT_MAP[match.group("unit").lower()]
        normalized_qty, normalized_unit, unit_note = _normalize_to_base_units(quantity, unit)
        parsed.append(
            {
                "name": clean_name,
                "quantity": normalized_qty,
                "unit": normalized_unit,
                "unit_note": unit_note,
            }
        )

    return parsed, unparsed


def _normalize_to_base_units(quantity: float, unit: str) -> tuple[float, str, str | None]:
    """г/гр -> кг (÷1000), л -> мл (×1000). Returns (qty, unit, optional note)."""
    if unit == "г":
        return round(quantity / 1000, 3), "кг", f"пересчитано из {quantity:g} г"
    if unit == "л":
        return round(quantity * 1000, 3), "мл", f"пересчитано из {quantity:g} л"
    return round(quantity, 3), unit, None


def _clean_name(raw_name: str) -> str:
    name = (raw_name or "").strip()
    # Drop separators before quantity: "Авокадо - 5 кг" -> "Авокадо"
    name = re.sub(r"\s*[-–—:;,]+\s*$", "", name)
    return " ".join(name.split())
