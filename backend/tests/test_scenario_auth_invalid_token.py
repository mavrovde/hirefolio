import pytest

# Scenario: Client sends an Authorization header with correct "Bearer" prefix but invalid token structure
# Expected: 401 Unauthorized (not 500 Internal Server Error)

@pytest.mark.asyncio
async def test_auth_scenario_malformed_token_header(clean_client):
    # clean_client is an async generator context manager when used in tests via pytest-asyncio?
    # No, the fixture is defined as `async def clean_client(...) -> AsyncGenerator`
    # In pytest-asyncio, you use it as `async for client in clean_client` or just `client` if it yields correctly?
    # Standard pytest fixture that yields is awaited by pytest.
    # The value injected into the test function is the YIELDED value.
    # So `clean_client` argument IS the `AsyncClient` instance yielded by the fixture.
    
    # Wait, my previous failure was "TypeError: 'async for' requires an object with __aiter__ method, got AsyncClient"
    # This means `clean_client` argument WAS the AsyncClient.
    
    client = clean_client
    response = await client.get("/api/app/auth/me", headers={"Authorization": "Bearer invalid.token.structure"})
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]
