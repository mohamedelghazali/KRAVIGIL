"""Central application settings. Load secrets from environment variables only."""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "KRAVIGIL"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://kravigil:change-me@localhost:5432/kravigil"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

settings = Settings()
