"""Название плана закупки: подпись, ответственный, статус в скобках."""

from datetime import date

from app.models import ProcurementBatch

BATCH_STATUS_LABELS: dict[str, str] = {
    "draft": "черновик",
    "parsed": "разобран",
    "matched": "проверен",
    "optimized": "распределён",
    "approved": "заказы",
    "exported": "экспорт",
}

RESPONSIBLE_OPTIONS = ("Женя", "Андрей")


def default_plan_label() -> str:
    return f"Заказ {date.today().strftime('%d.%m.%Y')}"


def batch_status_label(status: str) -> str:
    return BATCH_STATUS_LABELS.get(status, status)


def sync_batch_display_title(batch: ProcurementBatch) -> None:
    label = (batch.plan_label or default_plan_label()).strip()
    parts = [label]
    responsible = (batch.responsible or "").strip()
    if responsible:
        parts.append(responsible)
    status_label = batch_status_label(batch.status)
    batch.title = f"{' · '.join(parts)} ({status_label})"


def apply_batch_status(batch: ProcurementBatch, status: str) -> None:
    batch.status = status
    sync_batch_display_title(batch)


def init_new_batch(batch: ProcurementBatch, plan_label: str, responsible: str | None) -> None:
    label = (plan_label or "").strip() or default_plan_label()
    resp = (responsible or "").strip()
    if resp and resp not in RESPONSIBLE_OPTIONS:
        resp = ""
    batch.plan_label = label
    batch.responsible = resp or None
    batch.status = "draft"
    sync_batch_display_title(batch)
