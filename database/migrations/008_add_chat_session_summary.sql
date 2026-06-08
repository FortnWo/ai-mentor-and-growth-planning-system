-- UKL1: per-session rolling narrative summary for chat attention packaging

CREATE TABLE IF NOT EXISTS chat_session_summary (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    summary TEXT NOT NULL,
    summarized_through_message_id INT UNSIGNED NULL,
    message_count INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_session_summary_session FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_session_summary_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE KEY uq_chat_session_summary_session (session_id),
    INDEX idx_chat_session_summary_user (user_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
