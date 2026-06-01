-- Backfill NULL record_date so trend/stats align with timeline display.
UPDATE growth_records
SET record_date = COALESCE(DATE(occurred_at), DATE(created_at))
WHERE record_date IS NULL
  AND deleted_at IS NULL;
