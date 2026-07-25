from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/mavrov"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768  # nomic-embed-text uses 768 dimensions
    generation_model: str = "llama3.2"
    fast_generation_model: str = "llama3.2:1b"

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
    api_prefix: str = "/api/app"
    gemini_api_key: str = ""
    cv_version: str = "v1.0"

    # LinkedIn
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_public_id: str = ""
    linkedin_cookie_li_at: str = ""
    linkedin_cookie_jsessionid: str = ""
    linkedin_import_token: str = ""
    import_max_image_mb: int = 10

    # CORS
    cors_origins: str = "http://localhost:4200,https://mavrov.de,https://www.mavrov.de,http://mavrov.de,http://www.mavrov.de"

    # Default admin seeding
    default_admin_email: str = "admin@mavrov.de"
    default_admin_password: str = "admin"

    # Profile data (years API)
    profile_data_http_base: str = "http://frontend:80/assets"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
