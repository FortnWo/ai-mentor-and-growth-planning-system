-- UKL0: user knowledge layer slice storage
-- Run on existing databases; new installs use database/schema.sql

CREATE TABLE IF NOT EXISTS ukl_slice (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    slice_type VARCHAR(64) NOT NULL,
    source_module VARCHAR(64) NOT NULL,
    ref_type VARCHAR(32) NULL,
    ref_id INT UNSIGNED NULL,
    payload TEXT NOT NULL,
    version INT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ukl_slice_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE KEY uq_ukl_slice_identity (user_id, slice_type, ref_type, ref_id),
    INDEX idx_ukl_slice_user_type (user_id, slice_type),
    INDEX idx_ukl_slice_ref (ref_type, ref_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
