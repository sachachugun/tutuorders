-- Variant B stage 3: product specifications for supplier order comments

CREATE TABLE IF NOT EXISTS product_specs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_product_id INTEGER NOT NULL REFERENCES canonical_products(id) ON DELETE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  scope_type TEXT NOT NULL DEFAULT 'global'
    CHECK (scope_type IN (
      'global',
      'department',
      'location',
      'location_department',
      'supplier',
      'supplier_department',
      'supplier_location'
    )),
  scope_location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
  scope_department_id INTEGER REFERENCES departments(id) ON DELETE CASCADE,
  scope_supplier_id INTEGER REFERENCES suppliers(id) ON DELETE CASCADE,
  spec_text TEXT NOT NULL,
  append_to_supplier_order INTEGER NOT NULL DEFAULT 1,
  valid_from TEXT,
  valid_to TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_product_specs_product ON product_specs(canonical_product_id, is_active);
