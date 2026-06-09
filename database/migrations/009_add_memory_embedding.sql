-- UKL5: memory_fact vector storage (A3)
-- Run on existing databases; new installs use database/schema.sql

CREATE TABLE IF NOT EXISTS memory_embedding (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    slice_id INT UNSIGNED NOT NULL,
    model VARCHAR(64) NOT NULL,
    dimensions INT UNSIGNED NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_memory_embedding_slice (slice_id),
    INDEX idx_memory_embedding_user (user_id),
    CONSTRAINT fk_memory_embedding_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_embedding_slice FOREIGN KEY (slice_id) REFERENCES ukl_slice (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
