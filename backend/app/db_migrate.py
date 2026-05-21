from pathlib import Path

from sqlalchemy import text

from app.db import engine
from app.schema_repair import repair_department_and_spec_schema

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

ORDERED_MIGRATION_FILES = (
    "003_last_price_upload.sql",
    "004_locations_departments.sql",
    "005_products_and_skus.sql",
    "006_product_specs.sql",
    "008_procurement_batches.sql",
    "009_allocations.sql",
    "010_supplier_order_lines.sql",
    "011_procurement_batch_meta.sql",
)

# Older migration ids recorded before file renames (same SQL already applied).
_MIGRATION_LEGACY_IDS: dict[str, tuple[str, ...]] = {
    "004_locations_departments": ("004_locations_channels",),
}


def _ensure_schema_migrations_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              id TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
    )


def _applied_migration_ids(conn) -> set[str]:
    rows = conn.execute(text("SELECT id FROM schema_migrations")).fetchall()
    return {row[0] for row in rows}


def _is_migration_applied(conn, migration_id: str) -> bool:
    applied = _applied_migration_ids(conn)
    if migration_id in applied:
        return True
    for legacy_id in _MIGRATION_LEGACY_IDS.get(migration_id, ()):
        if legacy_id in applied:
            return True
    return False


def _mark_migration_applied(conn, migration_id: str) -> None:
    conn.execute(
        text("INSERT OR IGNORE INTO schema_migrations (id) VALUES (:id)"),
        {"id": migration_id},
    )


def _apply_last_price_upload_migration(conn) -> None:
    migration_id = "003_last_price_upload"
    if migration_id in _applied_migration_ids(conn):
        return

    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(suppliers)")).fetchall()}
    if "last_price_upload_at" not in columns:
        conn.execute(text("ALTER TABLE suppliers ADD COLUMN last_price_upload_at TEXT"))

    conn.execute(
        text(
            """
            UPDATE suppliers
            SET last_price_upload_at = updated_at
            WHERE last_price_upload_at IS NULL
              AND id IN (SELECT DISTINCT supplier_id FROM prices)
            """
        )
    )
    _mark_migration_applied(conn, migration_id)


def _execute_sql_script(conn, script: str) -> None:
    for statement in script.split(";"):
        lines = [
            line
            for line in statement.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        stmt = "\n".join(lines).strip()
        if stmt:
            conn.execute(text(stmt))


def _apply_sql_file_migration(conn, filename: str) -> None:
    migration_id = filename.removesuffix(".sql")
    if _is_migration_applied(conn, migration_id):
        if migration_id not in _applied_migration_ids(conn):
            _mark_migration_applied(conn, migration_id)
        return

    path = MIGRATIONS_DIR / filename
    if not path.exists():
        return

    _execute_sql_script(conn, path.read_text(encoding="utf-8"))
    _mark_migration_applied(conn, migration_id)


def run_pending_migrations() -> None:
    with engine.begin() as conn:
        _ensure_schema_migrations_table(conn)
        _apply_last_price_upload_migration(conn)
        for filename in ORDERED_MIGRATION_FILES:
            if filename == "003_last_price_upload.sql":
                continue
            _apply_sql_file_migration(conn, filename)

        repair_department_and_spec_schema(conn)


def ensure_schema() -> None:
    """Backward-compatible entry point used on app startup."""
    run_pending_migrations()
