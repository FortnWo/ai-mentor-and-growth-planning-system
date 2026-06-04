-- Migration 004: Add system_config and ai_usage_logs tables

CREATE TABLE IF NOT EXISTS system_config (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(128) NOT NULL UNIQUE COMMENT '配置键',
    `value` TEXT NULL COMMENT '配置值（敏感字段为 Fernet 密文）',
    is_encrypted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否加密存储',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_system_config_key (`key`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NULL COMMENT '调用用户（NULL 表示系统调用）',
    model VARCHAR(128) NOT NULL,
    prompt_tokens INT UNSIGNED NOT NULL DEFAULT 0,
    completion_tokens INT UNSIGNED NOT NULL DEFAULT 0,
    task VARCHAR(64) NULL COMMENT '调用场景（chat / profile / goal / etc.）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usage_user_id (user_id),
    INDEX idx_usage_created (created_at),
    INDEX idx_usage_model (model)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- risk_flag for users who exceed rate limit thresholds
ALTER TABLE users
    ADD COLUMN risk_flag TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '风险标记：0正常 1预警 2限速' AFTER enrollment_year;
