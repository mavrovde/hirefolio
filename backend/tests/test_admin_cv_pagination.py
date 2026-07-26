import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_cv_requests_pagination_empty(client: AsyncClient):
    """Test CV requests pagination with no data."""
    response = await client.get(f"{settings.api_prefix}/admin/cv/requests")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_cv_requests_search(client: AsyncClient, db_session):
    """Test CV requests search functionality."""
    from app.models.cv_request import CvRequest

    # Create test requests
    requests = [
        CvRequest(
            name="John Docker",
            email="john@docker.com",
            company="Docker Inc",
            message="Test message",
        ),
        CvRequest(
            name="Jane Python",
            email="jane@python.org",
            company="Python Foundation",
            message="Test message",
        ),
        CvRequest(
            name="Bob Smith",
            email="bob@docker.io",
            company="Tech Corp",
            message="Test message",
        ),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Search for "Docker"
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?search=Docker"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # John Docker and bob@docker.io

    # Search for "Python"
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?search=Python"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1  # Jane Python (Python in name and company)


@pytest.mark.asyncio
async def test_cv_requests_sorting(client: AsyncClient, db_session):
    """Test CV requests sorting."""
    from app.models.cv_request import CvRequest

    # Create requests
    requests = [
        CvRequest(
            name="Zebra User", email="z@test.com", company="Z Corp", message="Test"
        ),
        CvRequest(
            name="Alpha User", email="a@test.com", company="A Corp", message="Test"
        ),
        CvRequest(
            name="Beta User", email="b@test.com", company="B Corp", message="Test"
        ),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Sort by name ascending
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_by=name&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "Alpha User"
    assert data["items"][2]["name"] == "Zebra User"

    # Sort by name descending
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_by=name&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "Zebra User"
    assert data["items"][2]["name"] == "Alpha User"


@pytest.mark.asyncio
async def test_cv_requests_pagination(client: AsyncClient, db_session):
    """Test CV requests pagination."""
    from app.models.cv_request import CvRequest

    # Create 15 requests
    for i in range(15):
        db_session.add(
            CvRequest(
                name=f"User {i}",
                email=f"user{i}@test.com",
                company=f"Company {i}",
                message="Test",
            )
        )
    await db_session.commit()

    # Get first page
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?page=1&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert len(data["items"]) == 10
    assert data["total_pages"] == 2

    # Get second page
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?page=2&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5


@pytest.mark.asyncio
async def test_cv_versions_pagination_empty(client: AsyncClient):
    """Test CV versions pagination with no data."""
    response = await client.get(f"{settings.api_prefix}/admin/cv/versions")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_cv_versions_search(client: AsyncClient, db_session):
    """Test CV versions search functionality."""
    from app.models.cv_document import CvDocument

    # Create test documents
    documents = [
        CvDocument(filename="cv_v1.pdf", version="1.0", data=b"data", is_active=True),
        CvDocument(
            filename="resume_v2.pdf", version="2.0", data=b"data", is_active=False
        ),
        CvDocument(filename="cv_v3.pdf", version="3.0", data=b"data", is_active=False),
    ]
    for doc in documents:
        db_session.add(doc)
    await db_session.commit()

    # Search for "cv"
    response = await client.get(f"{settings.api_prefix}/admin/cv/versions?search=cv")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # cv_v1.pdf and cv_v3.pdf

    # Search for "2.0"
    response = await client.get(f"{settings.api_prefix}/admin/cv/versions?search=2.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["version"] == "2.0"


@pytest.mark.asyncio
async def test_cv_versions_sorting(client: AsyncClient, db_session):
    """Test CV versions sorting."""
    from app.models.cv_document import CvDocument

    # Create documents
    documents = [
        CvDocument(filename="z.pdf", version="3.0", data=b"data", is_active=False),
        CvDocument(filename="a.pdf", version="1.0", data=b"data", is_active=True),
        CvDocument(filename="m.pdf", version="2.0", data=b"data", is_active=False),
    ]
    for doc in documents:
        db_session.add(doc)
    await db_session.commit()

    # Sort by version ascending
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?sort_by=version&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["version"] == "1.0"
    assert data["items"][2]["version"] == "3.0"

    # Sort by filename descending
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?sort_by=filename&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["filename"] == "z.pdf"
    assert data["items"][2]["filename"] == "a.pdf"


@pytest.mark.asyncio
async def test_cv_versions_pagination(client: AsyncClient, db_session):
    """Test CV versions pagination."""
    from app.models.cv_document import CvDocument

    # Create 12 documents
    for i in range(12):
        db_session.add(
            CvDocument(
                filename=f"cv_{i}.pdf",
                version=f"{i}.0",
                data=b"data",
                is_active=i == 11,
            )
        )
    await db_session.commit()

    # Get first page
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?page=1&page_size=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 12
    assert len(data["items"]) == 5
    assert data["total_pages"] == 3

    # Get last page
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?page=3&page_size=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_cv_combined_search_sort_pagination(client: AsyncClient, db_session):
    """Test combining search, sort, and pagination for CV requests."""
    from app.models.cv_request import CvRequest

    # Create requests with Docker keyword
    requests = [
        CvRequest(
            name="Docker Zebra",
            email="z@docker.com",
            company="Docker Z",
            message="Test",
        ),
        CvRequest(
            name="Docker Alpha",
            email="a@docker.com",
            company="Docker A",
            message="Test",
        ),
        CvRequest(
            name="Docker Beta", email="b@docker.com", company="Docker B", message="Test"
        ),
        CvRequest(
            name="Python User", email="p@python.org", company="Python", message="Test"
        ),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Search for Docker, sort by name asc, page_size=2
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?search=Docker&sort_by=name&sort_order=asc&page=1&page_size=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["items"][0]["name"] == "Docker Alpha"
    assert data["items"][1]["name"] == "Docker Beta"

    # Get second page
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?search=Docker&sort_by=name&sort_order=asc&page=2&page_size=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Docker Zebra"
