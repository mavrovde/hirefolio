from pydantic_settings import BaseSettings, SettingsConfigDict

# SECURITY (issue #177): signing-secret values that must never be honoured. The
# first entry is the historical placeholder that used to be the *default* of
# ``jwt_secret_key`` — it is committed in a public repository, so any deployment
# still signing admin JWTs with it can have tokens forged without a credential.
# ``app.services.auth.get_jwt_secret_key`` rejects every value in this set.
INSECURE_JWT_SECRET_KEYS = frozenset(
    {
        "your-secret-key-change-in-production",
        "",
    }
)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/mavrov"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768  # nomic-embed-text uses 768 dimensions
    generation_model: str = "llama3.2"
    fast_generation_model: str = "llama3.2:1b"

    # Authentication
    #
    # SECURITY (issue #177): there is intentionally NO usable default signing
    # secret. ``JWT_SECRET_KEY`` MUST be supplied in any real deployment —
    # startup (see app.main lifespan) refuses to boot when it is empty or still
    # the historical placeholder (see INSECURE_JWT_SECRET_KEYS), so prod can
    # never sign admin JWTs with a publicly-known key. Generate one with:
    #   openssl rand -hex 32
    # Local dev / E2E set ``JWT_ALLOW_EPHEMERAL_SECRET=true`` instead and get a
    # random per-process secret, so no key has to be committed or injected into
    # CI (tokens simply do not survive a backend restart there).
    jwt_secret_key: str = ""
    jwt_allow_ephemeral_secret: bool = False
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
    # Fernet key (urlsafe-base64, 32 bytes) used to encrypt the per-user Gemini
    # API key at rest (see app.services.crypto / issue #143). Empty disables
    # field encryption (values stored/read as plaintext) so local/dev/E2E setups
    # keep working; production sets it to encrypt the paid credential at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet;
    # print(Fernet.generate_key().decode())"
    gemini_encryption_key: str = ""
    # Gemini model selection. Suggestion/tagging tasks (tags, title, slug,
    # summary) are cheap and use the flash-tier model by default; override via
    # GEMINI_MODEL / GEMINI_MODEL_FALLBACK. The fallback is only used when the
    # primary model is reported *unavailable* (HTTP 404), never on generic
    # errors — those fall through to the free local Ollama models instead of
    # making a second billable Gemini call.
    gemini_model: str = "gemini-2.5-flash"
    gemini_model_fallback: str = "gemini-2.0-flash"
    cv_version: str = "v1.0"

    # LinkedIn
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_public_id: str = ""
    linkedin_cookie_li_at: str = ""
    linkedin_cookie_jsessionid: str = ""
    linkedin_import_token: str = ""
    import_max_image_mb: int = 10
    # Directory where the saved LinkedIn login session (cookies) is stored. Must
    # live on a persistent, mounted volume (see docker-compose) so the session
    # survives container recreation/deploys instead of being wiped with /tmp.
    linkedin_cookies_dir: str = "/data/linkedin_cookies"

    # CORS
    cors_origins: str = "http://localhost:4200,https://mavrov.de,https://www.mavrov.de,http://mavrov.de,http://www.mavrov.de"

    # Default admin seeding.
    #
    # SECURITY (issue #142): there is intentionally NO weak default password.
    # ``ADMIN_PASSWORD`` MUST be provided in any real deployment; the lifespan
    # seed (see app.main) refuses to create a login-able default admin when this
    # is empty, so prod can never ship the historical ``admin``/``admin`` login.
    # Local dev / E2E seed their own throwaway credentials via
    # ``scripts/seed_e2e_user.py`` instead of relying on this path.
    default_admin_email: str = "admin@mavrov.de"
    admin_password: str = ""

    # Profile data (years API)
    profile_data_http_base: str = "http://frontend:80/assets"

    # Rate limiting (in-memory, per-process, per-client-IP). Generous defaults so
    # normal browsing/SSR is never affected — this is defense-in-depth against
    # scraping/abuse of unauthenticated public GETs, not a hard traffic quota.
    profile_rate_limit_requests: int = 100
    profile_rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
