from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://feedstream:feedstream@localhost:5433/feedstream"
    redis_url: str = "redis://localhost:6379/0"
    ais_api_key: str = ""
    app_env: str = "development"
    log_level: str = "INFO"
    debug_stats_token: str = "local-dev-token"
    enable_metrics: bool = True
    enable_docs: bool = True
    worker_metrics_port: int = 9100
    retention_days: int = 30
    retention_batch_size: int = 5000
    retention_interval_minutes: int = 1440
    public_base_url: str = "http://localhost:8000"
    github_repo_url: str = "https://github.com/Archangel-77/feedstream"


settings = Settings()


def get_settings() -> Settings:
    """Get settings instance."""
    return settings
