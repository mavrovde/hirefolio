import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.user import User
from app.services.auth import get_current_admin_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth_for_all():
    app.dependency_overrides[get_current_admin_user] = lambda: User(
        id=1, username="admin"
    )
    yield
    app.dependency_overrides.clear()


def test_sync_linkedin_profile_success(monkeypatch):
    mock_data = {"name": "Test User", "headline": "Software Engineer"}

    async def mock_sync_profile():
        return mock_data

    monkeypatch.setattr(
        "app.api.linkedin.linkedin_service.sync_profile", mock_sync_profile
    )

    response = client.get(
        f"{settings.api_prefix}/linkedin/profile-sync",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    assert response.json() == mock_data


def test_sync_linkedin_profile_value_error(monkeypatch):
    async def mock_sync_profile():
        raise ValueError("Missing credentials")

    monkeypatch.setattr(
        "app.api.linkedin.linkedin_service.sync_profile", mock_sync_profile
    )

    response = client.get(
        f"{settings.api_prefix}/linkedin/profile-sync",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 500
    assert "LinkedIn config error" in response.json()["detail"]


def test_sync_linkedin_profile_general_error(monkeypatch):
    async def mock_sync_profile():
        raise Exception("Unexpected failure")

    monkeypatch.setattr(
        "app.api.linkedin.linkedin_service.sync_profile", mock_sync_profile
    )

    response = client.get(
        f"{settings.api_prefix}/linkedin/profile-sync",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 500
    assert "LinkedIn profile sync failed" in response.json()["detail"]


def test_get_linkedin_posts_success(monkeypatch):
    mock_posts = [{"content": "Hello World", "url": "http://linkedin.com"}]

    async def mock_fetch_posts():
        return mock_posts

    monkeypatch.setattr(
        "app.api.linkedin.linkedin_service.fetch_posts", mock_fetch_posts
    )

    response = client.get(
        f"{settings.api_prefix}/linkedin/posts",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    assert response.json() == mock_posts


def test_get_linkedin_posts_value_error(monkeypatch):
    async def mock_fetch_posts():
        raise ValueError("Scraper block")

    monkeypatch.setattr(
        "app.api.linkedin.linkedin_service.fetch_posts", mock_fetch_posts
    )

    response = client.get(
        f"{settings.api_prefix}/linkedin/posts",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_get_linkedin_posts_general_error(monkeypatch):
    async def mock_fetch_posts():
        raise Exception("Crash")

    monkeypatch.setattr(
        "app.api.linkedin.linkedin_service.fetch_posts", mock_fetch_posts
    )

    response = client.get(
        f"{settings.api_prefix}/linkedin/posts",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 500
    assert "LinkedIn posts fetch failed" in response.json()["detail"]


def test_transfer_linkedin_post_success(monkeypatch):
    post_data = {
        "content": "This is a great new post about testing FastAPI.",
        "image_url": "https://example.com/image.png",
        "urn": "urn:li:activity:12345",
    }

    # Since we are not saving to a real db in TestClient, mock Db add/commit
    # Or rely on the mock db from get_db dependency override.
    # We will override dependencies globally in the test.
    from app.database import get_db

    class MockSession:
        def add(self, p):
            p.id = 999

        async def commit(self):
            pass

        async def refresh(self, p):
            pass

    app.dependency_overrides[get_db] = lambda: MockSession()

    response = client.post(
        f"{settings.api_prefix}/linkedin/transfer-post",
        json=post_data,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["message"] == "Post transferred successfully"


def test_transfer_linkedin_post_empty_content(monkeypatch):
    post_data = {
        "content": "A" * 60,
    }
    from app.database import get_db

    class MockSession:
        def add(self, p):
            p.id = 999

        async def commit(self):
            pass

        async def refresh(self, p):
            pass

    app.dependency_overrides[get_db] = lambda: MockSession()

    response = client.post(
        f"{settings.api_prefix}/linkedin/transfer-post",
        json=post_data,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200


def test_transfer_linkedin_post_long_empty_content(monkeypatch):
    # Hits line 87 because stripped title is empty, but content length > 50
    post_data = {
        "content": " " * 52,
    }
    from app.database import get_db

    class MockSession:
        def add(self, p):
            p.id = 999

        async def commit(self):
            pass

        async def refresh(self, p):
            pass

    app.dependency_overrides[get_db] = lambda: MockSession()

    response = client.post(
        f"{settings.api_prefix}/linkedin/transfer-post",
        json=post_data,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200


def test_transfer_linkedin_post_special_chars_only(monkeypatch):
    # Hits line 94 because regex strips everything into empty slug_base
    post_data = {
        "content": "!@#$ %^&*()",
    }
    from app.database import get_db

    class MockSession:
        def add(self, p):
            p.id = 999

        async def commit(self):
            pass

        async def refresh(self, p):
            pass

    app.dependency_overrides[get_db] = lambda: MockSession()

    response = client.post(
        f"{settings.api_prefix}/linkedin/transfer-post",
        json=post_data,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200


def test_transfer_linkedin_post_no_title_fallback(monkeypatch):
    post_data = {
        "content": "   ",
    }
    from app.database import get_db

    class MockSession:
        def add(self, p):
            p.id = 999

        async def commit(self):
            pass

        async def refresh(self, p):
            pass

    app.dependency_overrides[get_db] = lambda: MockSession()

    response = client.post(
        f"{settings.api_prefix}/linkedin/transfer-post",
        json=post_data,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200


def test_transfer_linkedin_post_db_error(monkeypatch):
    post_data = {"content": "Test"}

    from app.database import get_db

    class ErrorSession:
        def add(self, p):
            pass

        async def commit(self):
            raise Exception("DB Error")

        async def rollback(self):
            pass

    app.dependency_overrides[get_db] = lambda: ErrorSession()

    response = client.post(
        f"{settings.api_prefix}/linkedin/transfer-post",
        json=post_data,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 500
    assert "Transfer failed" in response.json()["detail"]

    app.dependency_overrides.clear()
