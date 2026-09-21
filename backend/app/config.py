from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


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

    # Evaluation persistence is deliberately separate from the legacy manual QA DB.
    evaluation_db: Path = Path('.specguard-data/evaluations.db')
    evaluation_artifacts: Path = Path('../benchmark-runs/web')
    evaluation_subjects: Path = Path(__file__).resolve().parents[2] / 'benchmarks/subjects'
    evaluation_runner_image: str = ''
    evaluation_retention_days: int = 7
    evaluation_storage_mb: int = 1024
    evaluation_run_storage_mb: int = 128

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
