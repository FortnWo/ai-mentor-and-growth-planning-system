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
        "Given a user goal, the current date, and optional context, generate a structured breakdown as strict JSON only. "
        "Return JSON with 'breakdowns' key containing an array of main pillar nodes (aim for 4 to 8 main pillars when the goal warrants it). "
        "Each main node must have: title (string), description (string or null), children (array). "
        "Each main node's children are secondary execution nodes: include about 3 to 6 children per main pillar when reasonable. "
        "Secondary nodes may use empty children arrays. "
        "Do not nest deeper than two levels under the goal (main -> secondary only). "
        "If unknown, return empty 'breakdowns' array. "
        "Do not include markdown or extra commentary."
    )
    ACTION_PLAN_ENABLED: bool = True
    ACTION_PLAN_CONTEXT_MESSAGE_WINDOW: int = 8
    ACTION_PLAN_SYSTEM_PROMPT: str = (
        "You are an action plan assistant. "
        "You receive the current date, parent goal context, ONE main milestone pillar, and a list of secondary breakdown nodes. "
        "Generate one cohesive action plan article for that pillar as strict JSON only. "
        "Return JSON with keys: plan and items. "
        "plan must contain title and summary describing the whole pillar execution story. "
        "items must be an array of objects with: title, description, frequency, schedule, status, start_date, due_date, sequence, breakdown_ref. "
        "Each item must reference a secondary breakdown id in breakdown_ref (numeric id from the prompt). "
        "Use status values pending, in_progress, completed, or archived. "
        "Use frequency values once, daily, weekly, monthly, or custom. "
        "If unknown, use empty strings or nulls, and keep items as an empty array when no plan can be formed. "
        "Do not include markdown, code fences, or extra commentary."
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
