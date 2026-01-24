from app.config import Settings


def test_default_settings():
    """Test that default settings are loaded correctly."""
    settings = Settings()
    assert (
        settings.database_url
        == "postgresql+asyncpg://postgres:postgres@localhost:5432/mavrov"
    )
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.embedding_dimensions == 768


def test_settings_from_env(monkeypatch):
    """Test that settings can be overridden by environment variables."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://custom:custom@custom:5432/custom"
    )
    monkeypatch.setenv("OLLAMA_URL", "http://custom-ollama:11434")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "512")

    settings = Settings()
    assert (
        settings.database_url == "postgresql+asyncpg://custom:custom@custom:5432/custom"
    )
    assert settings.ollama_url == "http://custom-ollama:11434"
    assert settings.embedding_model == "custom-model"
    assert settings.embedding_dimensions == 512
