"""One-time repairs for SQLite databases created during early variant B development."""

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _table_names(conn: Connection) -> set[str]:
    rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    return {row[0] for row in rows}


def _column_names(conn: Connection, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def repair_department_and_spec_schema(conn: Connection) -> None:
    tables = _table_names(conn)

    if "departments" not in tables:
        conn.execute(
            text(
                """
                CREATE TABLE departments (
                  id INTEGER PRIMARY KEY,
                  code TEXT NOT NULL UNIQUE,
                  name TEXT NOT NULL
                )
                """
            )
        )
        tables = _table_names(conn)

    obsolete_table = "channels"
    if obsolete_table in tables:
        dept_count = conn.execute(text("SELECT COUNT(*) FROM departments")).scalar() or 0
        if dept_count == 0:
            conn.execute(
                text(
                    f"""
                    INSERT OR IGNORE INTO departments (id, code, name)
                    SELECT id, code, name FROM {obsolete_table}
                    """
                )
            )
        conn.execute(text(f"DROP TABLE {obsolete_table}"))

    count = conn.execute(text("SELECT COUNT(*) FROM departments")).scalar() or 0
    if count == 0:
        conn.execute(
            text(
                """
                INSERT OR IGNORE INTO departments (id, code, name) VALUES
                  (1, 'kitchen', 'Кухня'),
                  (2, 'bar', 'Бар')
                """
            )
        )

    if "product_specs" not in _table_names(conn):
        return

    spec_cols = _column_names(conn, "product_specs")
    if "scope_channel_id" in spec_cols and "scope_department_id" not in spec_cols:
        conn.execute(text("ALTER TABLE product_specs RENAME COLUMN scope_channel_id TO scope_department_id"))

    for old_value, new_value in (
        ("channel", "department"),
        ("location_channel", "location_department"),
        ("supplier_channel", "supplier_department"),
    ):
        conn.execute(
            text("UPDATE product_specs SET scope_type = :new WHERE scope_type = :old"),
            {"old": old_value, "new": new_value},
        )
