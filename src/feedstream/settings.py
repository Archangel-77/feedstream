from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://feedstream:feedstream@localhost:5432/feedstream"
    redis_url: str = "redis://localhost:6379/0"
    ais_api_key: str = ""
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
