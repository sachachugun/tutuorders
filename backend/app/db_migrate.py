from sqlalchemy import text

from app.db import engine


def ensure_schema() -> None:
    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(suppliers)")).fetchall()
        }
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
