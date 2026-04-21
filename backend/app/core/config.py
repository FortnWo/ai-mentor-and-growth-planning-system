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
