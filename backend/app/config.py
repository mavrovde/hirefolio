from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mavrov"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768  # nomic-embed-text uses 768 dimensions
    generation_model: str = "tinyllama"

    # Authentication
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    class Config:
        env_file = ".env"


settings = Settings()
