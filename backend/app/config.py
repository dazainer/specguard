from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./specguard.db"

    # OpenAI
    openai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_temperature: float = 0.3
    ai_max_retries: int = 2

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    frontend_url: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
