-- Название плана и ответственный (отдельно от display title со статусом)
ALTER TABLE procurement_batches ADD COLUMN plan_label TEXT;
ALTER TABLE procurement_batches ADD COLUMN responsible TEXT;

UPDATE procurement_batches
SET plan_label = title
WHERE plan_label IS NULL;
