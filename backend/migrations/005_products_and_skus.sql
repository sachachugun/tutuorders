-- Variant B stage 2: canonical products and supplier SKU bindings

CREATE TABLE IF NOT EXISTS canonical_products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  default_unit TEXT NOT NULL DEFAULT 'кг'
    CHECK (default_unit IN ('кг', 'г', 'л', 'мл')),
  category TEXT,
  notes TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS supplier_skus (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_product_id INTEGER NOT NULL REFERENCES canonical_products(id) ON DELETE CASCADE,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
  price_id INTEGER REFERENCES prices(id) ON DELETE SET NULL,
  name_in_price TEXT NOT NULL,
  unit TEXT NOT NULL CHECK (unit IN ('кг', 'г', 'л', 'мл')),
  price REAL NOT NULL CHECK (price > 0),
  match_source TEXT NOT NULL DEFAULT 'manual'
    CHECK (match_source IN ('manual', 'ai', 'rule', 'import')),
  match_score REAL,
  is_preferred INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  UNIQUE (canonical_product_id, supplier_id, name_in_price)
);

CREATE INDEX IF NOT EXISTS idx_supplier_skus_lookup ON supplier_skus(canonical_product_id, supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_skus_supplier ON supplier_skus(supplier_id);
