-- Variant B stage 4.4: supplier order lines for export

CREATE TABLE IF NOT EXISTS supplier_order_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES procurement_batches(id) ON DELETE CASCADE,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  location_id INTEGER NOT NULL REFERENCES locations(id),
  department_id INTEGER NOT NULL REFERENCES departments(id),
  allocation_id INTEGER NOT NULL REFERENCES allocations(id) ON DELETE CASCADE,
  supplier_product_name TEXT NOT NULL,
  quantity REAL NOT NULL,
  unit TEXT NOT NULL CHECK (unit IN ('кг', 'г', 'л', 'мл')),
  unit_price REAL NOT NULL,
  amount REAL NOT NULL,
  spec_text TEXT,
  line_comment TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_supplier_order_export
  ON supplier_order_lines(batch_id, supplier_id, location_id, department_id);
