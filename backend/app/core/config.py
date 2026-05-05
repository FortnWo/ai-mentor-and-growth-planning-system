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
    LLM_SYSTEM_PROMPT: str | None = None
    PROFILE_EXTRACTION_ENABLED: bool = True
    PROFILE_EXTRACTION_MESSAGE_WINDOW: int = 14
    PROFILE_EXTRACTION_SYSTEM_PROMPT: str = (
        "You are a profile extraction assistant. "
        "Extract user profile signals from the dialogue and return strict JSON only. "
        "Use keys: interests, skills, goals, study_habits, personality, preferences. "
        "Each key must map to an array of short strings. "
        "If unknown, return an empty array for that key. "
        "Do not include markdown or extra commentary."
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
    RUN_LIVE_AI_TESTS: bool = False

    AUTH_SECRET_KEY: str = "change-me-in-production-with-a-long-secret-key"
    AUTH_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRES_MINUTES: int = 120

    BOOTSTRAP_ADMIN_USERNAME: str | None = None
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    BOOTSTRAP_ADMIN_PASSWORD: str | None = None
    BOOTSTRAP_ADMIN_FULL_NAME: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
