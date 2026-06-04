-- Layer 1: manual checks for AI usage stats (replace username as needed)
-- Run against the same database as the backend DATABASE_URL.

-- 1) Table exists
SHOW TABLES LIKE 'ai_usage_logs';

-- 2) Recent rows overview
SELECT id, user_id, model, task, prompt_tokens, completion_tokens, created_at
FROM ai_usage_logs
ORDER BY id DESC
LIMIT 20;

-- 3) Per-user filter (same logic as GET /admin/system/logs/usage?username=...)
SELECT COUNT(*) AS calls
FROM ai_usage_logs
WHERE user_id = (SELECT id FROM users WHERE username = '1234567890' LIMIT 1);

-- 4) Rows missing user_id (won't appear in per-user stats)
SELECT COUNT(*) AS null_user_rows FROM ai_usage_logs WHERE user_id IS NULL;

-- 5) Global totals for today
SELECT COUNT(*) AS calls,
       COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
       COALESCE(SUM(completion_tokens), 0) AS completion_tokens
FROM ai_usage_logs
WHERE DATE(created_at) = CURDATE();
