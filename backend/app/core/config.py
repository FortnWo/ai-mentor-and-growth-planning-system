from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AI Mentor & Growth Planning System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "mysql+pymysql://user:password@localhost:3306/ai_mentor_db"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    LLM_API_KEY: str | None = None
    LLM_API_BASE_URL: str | None = None
    LLM_MODEL: str | None = None
    LLM_SYSTEM_PROMPT: str = (
        "你是一位支持型大学 AI 导师，耐心倾听学生的困惑与目标，"
        "用清晰、鼓励的语气给出可执行的建议，避免空泛说教。"
    )
    PROFILE_EXTRACTION_ENABLED: bool = True
    PROFILE_EXTRACTION_MESSAGE_WINDOW: int = 14
    PROFILE_EXTRACTION_SYSTEM_PROMPT: str = (
        "You are a profile extraction mentor. "
        "Extract user profile signals from the dialogue and return strict JSON only. "
        "Use keys: interests, skills, goals, study_habits, personality, preferences. "
        "Each key must map to an array of short strings. "
        "If unknown, return an empty array for that key. "
        "Do not include markdown or extra commentary."
    )
    PORTRAIT_SUMMARY_SYSTEM_PROMPT: str = (
        "You are a student growth mentor. "
        "Write a concise portrait summary in Chinese (second person, 150-250 characters). "
        "Use only the trait signals provided in the user message. "
        "Do not invent facts. "
        "If no traits are provided, reply exactly: 尚未形成可描述的画像特质，建议多与 AI 导师交流或补充画像字段。"
    )
    GOAL_BREAKDOWN_ENABLED: bool = True
    GOAL_BREAKDOWN_MESSAGE_WINDOW: int = 5
    GOAL_BREAKDOWN_SYSTEM_PROMPT: str = (
        "You are a goal breakdown assistant. "
        "Given a user goal and optional context, generate a structured breakdown as strict JSON only. "
        "Return JSON with 'breakdowns' key containing an array of breakdown nodes. "
        "Each node must have: title (string), description (string or null), children (array of nodes). "
        "Nodes can be nested recursively. "
        "If unknown, return empty 'breakdowns' array. "
        "Do not include markdown or extra commentary."
    )
    ACTION_PLAN_ENABLED: bool = True
    ACTION_PLAN_CONTEXT_MESSAGE_WINDOW: int = 8
    ACTION_PLAN_SYSTEM_PROMPT: str = (
        "You are an action plan assistant. "
        "Given a user goal, its breakdown tree, and optional profile context, generate a practical action plan as strict JSON only. "
        "Return JSON with keys: plan and items. "
        "plan must contain title and summary. "
        "items must be an array of objects with: title, description, frequency, schedule, status, start_date, due_date, sequence, breakdown_ref. "
        "Use status values pending, in_progress, completed, or archived. "
        "Use frequency values once, daily, weekly, monthly, or custom. "
        "If unknown, use empty strings or nulls, and keep items as an empty array when no plan can be formed. "
        "Do not include markdown, code fences, or extra commentary."
    )
    SESSION_TITLE_SYSTEM_PROMPT: str = (
        "You are a chat session title generator. "
        "Given the first user message and assistant reply, output a concise Chinese title (4-16 characters). "
        "Return only the title text: no quotes, punctuation, markdown, or explanation."
    )
    ADMIN_LLM_SYSTEM_PROMPT: str = (
        "你是一个专业全能的系统管理助手。"
        "你可以通过工具查询系统数据库、获取日志和统计信息，用自然语言为管理员提供精准答复。"
        "回答要简洁专业，数据准确。禁止执行任何写操作或 DDL 语句。"
    )
    APP_SECRET_KEY: str = "ai-mentor-default-secret-change-in-production"
    RUN_LIVE_AI_TESTS: bool = False

    # UKL (user knowledge layer); UKL0: profile dual-write; UKL1: chat attention packaging when enabled
    UKL_ENABLED: bool = False
    CHAT_WORK_MEMORY_MAX_MESSAGES: int = 12
    CHAT_SUMMARY_USE_THRESHOLD: int = 16
    CHAT_SESSION_SUMMARY_ENABLED: bool = True
    CHAT_SESSION_SUMMARY_SYSTEM_PROMPT: str = (
        "你是对话摘要助手。根据已有摘要与新增对话，输出更新后的中文会话摘要（第二人称，150-400字）。"
        "保留关键事实、目标、情绪与未决事项；不要编造；不要输出 markdown 或标题。"
    )

    AUTH_SECRET_KEY: str = "change-me-in-production-with-a-long-secret-key"
    AUTH_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRES_MINUTES: int = 120

    BOOTSTRAP_ADMIN_USERNAME: str | None = None
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    BOOTSTRAP_ADMIN_PASSWORD: str | None = None
    BOOTSTRAP_ADMIN_FULL_NAME: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
