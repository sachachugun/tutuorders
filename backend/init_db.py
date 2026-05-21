import sqlite3
from pathlib import Path

from app.db_migrate import run_pending_migrations


def main() -> None:
    root = Path(__file__).parent
    db_path = root / "app.db"
    m1 = root / "migrations" / "001_init.sql"
    m2 = root / "migrations" / "002_seed.sql"

    if not m1.exists() or not m2.exists():
        raise SystemExit("Migration files not found in backend/migrations")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(m1.read_text(encoding="utf-8"))
        cur.executescript(m2.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()

    run_pending_migrations()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        suppliers = cur.execute(
            "SELECT id, name, min_order_amount FROM suppliers ORDER BY id"
        ).fetchall()
        print(f"DB initialized: {db_path}")
        print(f"Suppliers count: {len(suppliers)}")
        for row in suppliers:
            print(row)

        locations = cur.execute(
            "SELECT id, code, name FROM locations ORDER BY sort_order, id"
        ).fetchall()
        print(f"Locations count: {len(locations)}")
        for row in locations:
            print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
