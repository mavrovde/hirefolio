import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# When running under pytest, allow a fallback JWT secret so tests work without
# requiring the env var. In production the startup guard in main.py enforces it.
_TESTING = os.getenv("TESTING", "false").lower() == "true"
_JWT_FALLBACK = "test-secret-key-for-pytest" if _TESTING else ""


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/mavrov"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768  # nomic-embed-text uses 768 dimensions
    generation_model: str = "llama3.2"
    fast_generation_model: str = "tinyllama"

    # Authentication
    jwt_secret_key: str = _JWT_FALLBACK  # Set via JWT_SECRET_KEY env var (required in production)
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    admin_email: str = "admin@mavrov.de"
    api_prefix: str = "/api/app"
    gemini_api_key: str = ""
    cv_version: str = "v1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
