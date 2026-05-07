INSERT OR IGNORE INTO suppliers (id, name, min_order_amount, updated_at)
VALUES
  (1, 'Кулинарная студия', 20000, datetime('now')),
  (2, 'Домпродукт', 30000, datetime('now'));

INSERT OR IGNORE INTO settings (key, value) VALUES
  ('folder_id', ''),
  ('model_name', 'yandexgpt-pro');
