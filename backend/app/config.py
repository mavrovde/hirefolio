from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/mavrov"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768  # nomic-embed-text uses 768 dimensions
    generation_model: str = "tinyllama"

    # Authentication
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    admin_email: str = "admin@mavrov.de"
    cv_version: str = "v1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
