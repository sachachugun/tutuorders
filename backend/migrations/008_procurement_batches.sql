-- Variant B stage 4: procurement plan and demand lines

CREATE TABLE IF NOT EXISTS procurement_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'parsed', 'matched', 'optimized', 'approved', 'exported')),
  optimizer_mode TEXT NOT NULL DEFAULT 'milp'
    CHECK (optimizer_mode IN ('milp', 'greedy_fallback', 'manual')),
  optimizer_config TEXT,
  total_amount REAL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_by TEXT,
  approved_at TEXT
);

CREATE TABLE IF NOT EXISTS demand_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES procurement_batches(id) ON DELETE CASCADE,
  location_id INTEGER NOT NULL REFERENCES locations(id),
  department_id INTEGER NOT NULL REFERENCES departments(id),
  canonical_product_id INTEGER REFERENCES canonical_products(id),
  raw_text TEXT NOT NULL,
  quantity REAL NOT NULL,
  unit TEXT NOT NULL CHECK (unit IN ('кг', 'г', 'л', 'мл')),
  normalized_quantity REAL,
  normalized_unit TEXT,
  parse_status TEXT NOT NULL DEFAULT 'ok'
    CHECK (parse_status IN ('ok', 'unparsed', 'needs_product')),
  line_notes TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_demand_lines_batch ON demand_lines(batch_id);
CREATE INDEX IF NOT EXISTS idx_demand_lines_group ON demand_lines(batch_id, canonical_product_id);
