from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AI Mentor & Growth Planning System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "mysql+pymysql://user:password@localhost:3306/ai_mentor_db"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
