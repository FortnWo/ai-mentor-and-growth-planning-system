-- AI Mentor & Growth Planning System
-- Initial database schema
-- Run this script once to set up the database.

CREATE DATABASE IF NOT EXISTS ai_mentor_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ai_mentor_db;

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
