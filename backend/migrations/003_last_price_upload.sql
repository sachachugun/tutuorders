-- Дата последней загрузки прайса (отдельно от updated_at карточки поставщика)
ALTER TABLE suppliers ADD COLUMN last_price_upload_at TEXT;
