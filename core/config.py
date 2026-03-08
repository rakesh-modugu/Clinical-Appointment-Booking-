"""
Pydantic settings loader — reads from .env automatically.
Access settings anywhere via: from core.config import settings
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: str
    ELEVENLABS_API_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
