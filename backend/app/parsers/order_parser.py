import re

LINE_RE = re.compile(
    r"^\s*(?P<name>.+?)\s+(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>кг|kg|г|гр|л|l|мл|ml)\s*$",
    re.IGNORECASE,
)
LINE_PAREN_RE = re.compile(
    r"^\s*(?P<name>.+?)\s*\(\s*(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>кг|kg|г|гр|л|l|мл|ml)\s*\)\s*$",
    re.IGNORECASE,
)

UNIT_MAP = {
    "кг": "кг",
    "kg": "кг",
    "г": "г",
    "гр": "г",
    "л": "л",
    "l": "л",
    "мл": "мл",
    "ml": "мл",
}


def _parse_line_match(match: re.Match[str]) -> dict:
    quantity = float(match.group("quantity").replace(",", "."))
    clean_name = _clean_name(match.group("name"))
    unit_key = match.group("unit").lower()
    unit = UNIT_MAP.get(unit_key, "кг")
    normalized_qty, normalized_unit, unit_note = _normalize_to_base_units(quantity, unit)
    return {
        "name": clean_name,
        "quantity": normalized_qty,
        "unit": normalized_unit,
        "unit_note": unit_note,
    }


def parse_single_line(line: str) -> dict | None:
    text = (line or "").strip()
    if not text:
        return None
    for pattern in (LINE_RE, LINE_PAREN_RE):
        match = pattern.match(text)
        if match:
            return _parse_line_match(match)
    return None


def parse_order_text(order_text: str) -> tuple[list[dict], list[str]]:
    parsed: list[dict] = []
    unparsed: list[str] = []

    for raw_line in order_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        item = parse_single_line(line)
        if item:
            parsed.append(item)
        else:
            unparsed.append(line)

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
