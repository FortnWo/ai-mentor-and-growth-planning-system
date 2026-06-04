-- Run on existing databases that were created before portrait summary columns were added.
-- New installs can use database/schema.sql directly.

ALTER TABLE user_profile
    ADD COLUMN portrait_summary TEXT NULL AFTER last_extracted_at,
    ADD COLUMN portrait_summary_at DATETIME NULL AFTER portrait_summary;
