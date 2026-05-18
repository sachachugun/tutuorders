PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS suppliers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  min_order_amount REAL NOT NULL DEFAULT 0 CHECK (min_order_amount >= 0),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_price_upload_at TEXT
);

CREATE TABLE IF NOT EXISTS prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  supplier_id INTEGER NOT NULL,
  name_in_price TEXT NOT NULL,
  unit TEXT NOT NULL CHECK (unit IN ('кг', 'г', 'л', 'мл')),
  price REAL NOT NULL CHECK (price > 0),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prices_supplier_id ON prices(supplier_id);
CREATE INDEX IF NOT EXISTS idx_prices_supplier_name ON prices(supplier_id, name_in_price);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
