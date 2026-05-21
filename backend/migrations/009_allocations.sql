-- Variant B stage 4.3: supplier allocations per demand line

CREATE TABLE IF NOT EXISTS allocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES procurement_batches(id) ON DELETE CASCADE,
  demand_line_id INTEGER NOT NULL UNIQUE REFERENCES demand_lines(id) ON DELETE CASCADE,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  supplier_sku_id INTEGER NOT NULL REFERENCES supplier_skus(id),
  quantity REAL NOT NULL,
  unit TEXT NOT NULL CHECK (unit IN ('кг', 'г', 'л', 'мл')),
  unit_price REAL NOT NULL,
  amount REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'optimizer'
    CHECK (source IN ('optimizer', 'manual_override'))
);

CREATE INDEX IF NOT EXISTS idx_allocations_batch ON allocations(batch_id);

CREATE TABLE IF NOT EXISTS supplier_order_totals (
  batch_id INTEGER NOT NULL REFERENCES procurement_batches(id) ON DELETE CASCADE,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  amount REAL NOT NULL,
  min_order_amount REAL NOT NULL,
  min_order_passed INTEGER NOT NULL,
  PRIMARY KEY (batch_id, supplier_id)
);
