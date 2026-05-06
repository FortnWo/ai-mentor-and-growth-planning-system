-- AI Mentor & Growth Planning System
-- Initial database schema
-- Run this script once to set up the database.

CREATE DATABASE IF NOT EXISTS ai_mentor_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ai_mentor_test;

-- -------------------------------------------------------
-- Users
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(100)  NOT NULL UNIQUE,
    email           VARCHAR(255)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    role            ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    is_active       TINYINT(1)    NOT NULL DEFAULT 1,
    admin_permission_level ENUM('full', 'limited') NULL,
    admin_permissions JSON NULL,
    admin_expires_at DATETIME NULL,
    last_login_at   DATETIME NULL,
    full_name       VARCHAR(255)  NULL,
    major           VARCHAR(255)  NULL,
    year_of_study   TINYINT UNSIGNED NULL,
    bio             TEXT          NULL,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------
-- Chat sessions
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    title       VARCHAR(255) NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------
-- Chat messages
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id  INT UNSIGNED NOT NULL,
    role        ENUM('user', 'assistant') NOT NULL,
    content     TEXT         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_messages_session FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
    INDEX idx_messages_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------
-- User extended profiles
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_extended_profiles (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id             INT UNSIGNED NOT NULL UNIQUE,
    interests           TEXT NULL,
    skills              TEXT NULL,
    goals               TEXT NULL,
    study_habits        TEXT NULL,
    personality         TEXT NULL,
    preferences         TEXT NULL,
    last_extracted_at   DATETIME NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_extended_profiles_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_extended_profiles_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -------------------------------------------------------
-- Goals
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS goals (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         INT UNSIGNED NOT NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    status          ENUM('active', 'completed', 'archived') NOT NULL DEFAULT 'active',
    priority        ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
    target_date     DATE NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_goals_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_goals_user (user_id),
    INDEX idx_goals_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------
-- Goal breakdowns (tree structure)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS goal_breakdowns (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    goal_id         INT UNSIGNED NOT NULL,
    parent_id       INT UNSIGNED NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    level           TINYINT UNSIGNED NOT NULL DEFAULT 0,
    sequence        SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    status          ENUM('pending', 'in_progress', 'completed') NOT NULL DEFAULT 'pending',
    due_date        DATE NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_breakdowns_goal FOREIGN KEY (goal_id) REFERENCES goals (id) ON DELETE CASCADE,
    CONSTRAINT fk_breakdowns_parent FOREIGN KEY (parent_id) REFERENCES goal_breakdowns (id) ON DELETE CASCADE,
    INDEX idx_breakdowns_goal (goal_id),
    INDEX idx_breakdowns_parent (parent_id),
    INDEX idx_breakdowns_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------
-- Action plans
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_plans (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    goal_id INT UNSIGNED NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    summary TEXT NULL,
    status ENUM('pending', 'in_progress', 'completed', 'archived', 'failed') NOT NULL DEFAULT 'pending',
    error_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_action_plans_goal FOREIGN KEY (goal_id) REFERENCES goals (id) ON DELETE CASCADE,
    INDEX idx_action_plans_goal (goal_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
-- -------------------------------------------------------
-- Action plan items
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_plan_items (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    plan_id INT UNSIGNED NOT NULL,
    breakdown_id INT UNSIGNED NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    frequency ENUM('once', 'daily', 'weekly', 'monthly', 'custom') NOT NULL DEFAULT 'custom',
    schedule TEXT NULL,
    status ENUM('pending', 'in_progress', 'completed', 'archived', 'failed') NOT NULL DEFAULT 'pending',
    start_date DATE NULL,
    due_date DATE NULL,
    sequence SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_action_plan_items_plan FOREIGN KEY (plan_id) REFERENCES action_plans (id) ON DELETE CASCADE,
    CONSTRAINT fk_action_plan_items_breakdown FOREIGN KEY (breakdown_id) REFERENCES goal_breakdowns (id) ON DELETE SET NULL,
    INDEX idx_action_plan_items_plan (plan_id),
    INDEX idx_action_plan_items_breakdown (breakdown_id),
    INDEX idx_action_plan_items_sequence (sequence)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;