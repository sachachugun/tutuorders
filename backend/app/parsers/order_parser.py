import re

UNIT_PATTERN = r"кг|kg|г|гр|л|l|мл|ml"
QTY_TOKEN = r"\d+(?:[.,]\d+)?|0\d+"

LINE_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s+(?P<quantity>{QTY_TOKEN})\s*(?P<unit>{UNIT_PATTERN})\s*$",
    re.IGNORECASE,
)
LINE_PAREN_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s*\(\s*(?P<quantity>{QTY_TOKEN})\s*(?P<unit>{UNIT_PATTERN})\s*\)\s*$",
    re.IGNORECASE,
)
LINE_QTY_ONLY_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s+(?P<quantity>{QTY_TOKEN})\s*$",
    re.IGNORECASE,
)
LINE_PACKS_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s+(?P<packs>\d+)\s+пачек\s+по\s+(?P<per_pack>{QTY_TOKEN})\s*$",
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

# Хвостовые пометки после количества: «12 кг не крупные»
TRAILING_NOTE_RE = re.compile(
    r"\s+(?:"
    r"не\s+крупн\w*|"
    r"крупн\w*|"
    r"мелк\w*"
    r")\s*$",
    re.IGNORECASE,
)


def _preprocess_line(line: str) -> tuple[str, str | None]:
    """Нормализация строки спроса; возвращает (текст, заметка если была отрезана)."""
    text = " ".join((line or "").strip().split())
    if not text:
        return "", None

    note_parts: list[str] = []
    note_match = TRAILING_NOTE_RE.search(text)
    if note_match:
        note_parts.append(note_match.group(0).strip())
        text = text[: note_match.start()].strip()

    # «редис - 4 кг», «редис - 4кг»
    text = re.sub(r"\s*[-–—:]\s*(?=\d)", " ", text)
    # «5кг» → «5 кг»
    text = re.sub(
        rf"({QTY_TOKEN})\s*({UNIT_PATTERN})\b",
        r"\1 \2",
        text,
        flags=re.IGNORECASE,
    )
    text = " ".join(text.split())
    note = "; ".join(note_parts) if note_parts else None
    return text, note


def _parse_quantity_token(raw: str) -> float:
    """
    Кг по умолчанию.
    - 7, 14 → целые килограммы
    - 0.6, 0,6 → как записано
    - 03, 025 → «0,3» / «0,25» кг (ведущий ноль = запятая после нуля): 03 → 300 г
    """
    s = (raw or "").strip().replace(",", ".")
    if not s:
        raise ValueError("empty quantity")
    if "." in s:
        return float(s)
    if s.startswith("0") and len(s) > 1 and s.isdigit():
        # 03 → 0.3, 025 → 0.25, 0125 → 0.125
        return float(f"0.{s[1:]}")
    return float(int(s))


def _parse_line_match(match: re.Match[str], unit_note: str | None = None) -> dict:
    quantity = _parse_quantity_token(match.group("quantity"))
    clean_name = _clean_name(match.group("name"))
    unit_key = match.group("unit").lower()
    unit = UNIT_MAP.get(unit_key, "кг")
    normalized_qty, normalized_unit, convert_note = _normalize_to_base_units(quantity, unit)
    notes = [n for n in (unit_note, convert_note) if n]
    return {
        "name": clean_name,
        "quantity": normalized_qty,
        "unit": normalized_unit,
        "unit_note": "; ".join(notes) if notes else None,
    }


def _parse_qty_only_match(match: re.Match[str], unit_note: str | None = None) -> dict:
    quantity = _parse_quantity_token(match.group("quantity"))
    clean_name = _clean_name(match.group("name"))
    normalized_qty, normalized_unit, convert_note = _normalize_to_base_units(quantity, "кг")
    notes = [n for n in (unit_note, convert_note) if n]
    return {
        "name": clean_name,
        "quantity": normalized_qty,
        "unit": normalized_unit,
        "unit_note": "; ".join(notes) if notes else None,
    }


def _parse_packs_match(match: re.Match[str], unit_note: str | None = None) -> dict:
    packs = int(match.group("packs"))
    per_pack = _parse_quantity_token(match.group("per_pack"))
    total_kg = round(packs * per_pack, 3)
    clean_name = _clean_name(match.group("name"))
    pack_note = f"{packs} пачек по {per_pack:g} кг"
    notes = [n for n in (unit_note, pack_note) if n]
    return {
        "name": clean_name,
        "quantity": total_kg,
        "unit": "кг",
        "unit_note": "; ".join(notes) if notes else None,
    }


def parse_single_line(line: str) -> dict | None:
    text = (line or "").strip()
    if not text:
        return None

    prepared, trailing_note = _preprocess_line(text)
    if not prepared:
        return None

    for pattern, parser in (
        (LINE_PACKS_RE, _parse_packs_match),
        (LINE_RE, _parse_line_match),
        (LINE_PAREN_RE, _parse_line_match),
        (LINE_QTY_ONLY_RE, _parse_qty_only_match),
    ):
        match = pattern.match(prepared)
        if match:
            return parser(match, trailing_note)
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
            item["source_line"] = line
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
    name = re.sub(r"\s*[-–—:;,]+\s*$", "", name)
    return " ".join(name.split())
