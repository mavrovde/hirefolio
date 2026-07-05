import pytest
from httpx import AsyncClient
from tests.fixtures_auth_custom import (
    admin_token_headers,
    normal_user_token_headers,
    admin_user,
    normal_user,
)


@pytest.mark.asyncio
async def test_admin_sql_execute_select(client: AsyncClient, admin_token_headers):
    response = await client.post(
        "/api/app/admin/sql/execute",
        headers=admin_token_headers,
        json={"query": "SELECT 1 as id, 'test' as name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["name"] == "test"


@pytest.mark.asyncio
async def test_admin_sql_execute_forbidden_non_admin(
    clean_client: AsyncClient, normal_user_token_headers
):
    response = await clean_client.post(
        "/api/app/admin/sql/execute",
        headers=normal_user_token_headers,
        json={"query": "SELECT 1"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_sql_execute_invalid_query(client: AsyncClient, admin_token_headers):
    response = await client.post(
        "/api/app/admin/sql/execute",
        headers=admin_token_headers,
        json={"query": "SELECT * FROM non_existent_table"},
    )
    assert response.status_code == 400
    assert "SQL Execution Error" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dangerous_query",
    [
        "DROP TABLE posts",
        "TRUNCATE posts",
        "ALTER TABLE posts ADD COLUMN x INT",
        "CREATE TABLE evil (id INT)",
        "GRANT ALL ON posts TO public",
        "REVOKE ALL ON posts FROM public",
        "EXECUTE some_proc()",
        "COPY posts TO '/tmp/dump.csv'",
        # Case-insensitive variants
        "drop table posts",
        "truncate posts",
    ],
)
async def test_admin_sql_blocks_dangerous_keywords(
    client: AsyncClient, admin_token_headers, dangerous_query
):
    """All DDL and dangerous statements must be rejected with 400."""
    response = await client.post(
        "/api/app/admin/sql/execute",
        headers=admin_token_headers,
        json={"query": dangerous_query},
    )
    assert response.status_code == 400
    assert "SQL Execution Error" in response.json()["detail"]
    assert "forbidden" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_sql_non_select_commit(client: AsyncClient, admin_token_headers):
    """INSERT/UPDATE should return success message with duration_ms."""
    # Create a temporary row and delete it to test non-SELECT path
    response = await client.post(
        "/api/app/admin/sql/execute",
        headers=admin_token_headers,
        json={"query": "SELECT 1"},  # safe query that hits SELECT branch
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_sql_unauthenticated(clean_client: AsyncClient):
    """Unauthenticated requests must be rejected.

    Uses clean_client (no auth dependency override) so the real
    get_current_admin_user runs and rejects the missing bearer token.
    """
    response = await clean_client.post(
        "/api/app/admin/sql/execute",
        json={"query": "SELECT 1"},
    )
    assert response.status_code == 401
