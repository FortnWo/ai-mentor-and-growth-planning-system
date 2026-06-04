-- Migration 002: Add phone, address, enrollment_year to users table
-- enrollment_year stores the year the student enrolled; year_of_study is computed at runtime

ALTER TABLE users
    ADD COLUMN phone VARCHAR(20) NULL COMMENT '手机号码' AFTER bio,
    ADD COLUMN address VARCHAR(500) NULL COMMENT '地址' AFTER phone,
    ADD COLUMN enrollment_year SMALLINT UNSIGNED NULL COMMENT '入学年份，用于运行时计算年级' AFTER address;

-- Index for filtering by enrollment year
ALTER TABLE users
    ADD INDEX idx_users_enrollment_year (enrollment_year);
