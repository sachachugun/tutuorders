-- Variant B stage 1: locations and departments (кухня / бар)

CREATE TABLE IF NOT EXISTS locations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL
);

INSERT OR IGNORE INTO departments (id, code, name) VALUES
  (1, 'kitchen', 'Кухня'),
  (2, 'bar', 'Бар');

INSERT OR IGNORE INTO locations (id, code, name, sort_order, is_active) VALUES
  (1, 'loc_1', 'Локация 1', 1, 1),
  (2, 'loc_2', 'Локация 2', 2, 1),
  (3, 'loc_3', 'Локация 3', 3, 1),
  (4, 'loc_4', 'Локация 4', 4, 1);
