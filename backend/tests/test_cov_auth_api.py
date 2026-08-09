"""Coverage tests for app.api.auth.

These call the endpoint coroutines directly (rather than via the ASGI
httpx transport) so that the endpoint bodies execute in the same thread
that coverage is tracing, and so that they exercise the real branches:
- login: user not found, wrong password, inactive user, and the full
  success path that mints a JWT.
- change_password: wrong old password branch and the successful update
  path (including the trailing ``return``).

They assert real behaviour, not just import success.
"""

import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.auth import (
    ChangePasswordRequest,
    TokenResponse,
    UpdateGeminiKeyRequest,
    UserResponse,
    change_password,
    get_me,
    login,
    update_gemini_key,
)
from app.config import settings
from app.models.user import User
from app.services.auth import get_password_hash, verify_password


def _form(username: str, password: str) -> OAuth2PasswordRequestForm:
    return OAuth2PasswordRequestForm(username=username, password=password)


@pytest.mark.asyncio
async def test_login_success_direct(db_session):
    """Full success path (lines 50-76): mints a valid token."""
    password = "s3cret-pass"
    user = User(
        username="covloginok",
        email="covloginok@example.com",
        hashed_password=get_password_hash(password),
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()

    result = await login(form_data=_form("covloginok", password), db=db_session)

    assert isinstance(result, TokenResponse)
    assert result.token_type == "bearer"
    assert result.access_token
    assert result.expires_in == settings.jwt_expiration_minutes * 60


@pytest.mark.asyncio
async def test_login_user_not_found(db_session):
    """Missing user -> 401 (line 53 truthy via `not user`)."""
    with pytest.raises(HTTPException) as exc:
        await login(form_data=_form("nobody-here", "whatever"), db=db_session)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Incorrect username or password"


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    """User exists but password is wrong -> 401 (line 53 password branch)."""
    user = User(
        username="covloginbad",
        email="covloginbad@example.com",
        hashed_password=get_password_hash("the-right-one"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await login(form_data=_form("covloginbad", "the-wrong-one"), db=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user_direct(db_session):
    """Inactive user -> 400 (lines 64-67)."""
    password = "inactive-pass"
    user = User(
        username="covlogininactive",
        email="covlogininactive@example.com",
        hashed_password=get_password_hash(password),
        is_active=False,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await login(form_data=_form("covlogininactive", password), db=db_session)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Inactive user"


@pytest.mark.asyncio
async def test_change_password_success_direct(db_session):
    """Successful password change hits the trailing return (line 119)."""
    old_password = "old-pass-123"
    new_password = "new-pass-456"
    user = User(
        username="covchangepw",
        email="covchangepw@example.com",
        hashed_password=get_password_hash(old_password),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    payload = ChangePasswordRequest(
        old_password=old_password, new_password=new_password
    )
    result = await change_password(
        password_data=payload, current_user=user, db=db_session
    )

    assert result is None
    # The stored hash must now verify against the new password only.
    await db_session.refresh(user)
    assert verify_password(new_password, user.hashed_password)
    assert not verify_password(old_password, user.hashed_password)


@pytest.mark.asyncio
async def test_change_password_wrong_old_direct(db_session):
    """Wrong old password -> 400 (lines 108-111)."""
    user = User(
        username="covchangepwbad",
        email="covchangepwbad@example.com",
        hashed_password=get_password_hash("real-old"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    payload = ChangePasswordRequest(old_password="not-real", new_password="whatever")
    with pytest.raises(HTTPException) as exc:
        await change_password(password_data=payload, current_user=user, db=db_session)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Incorrect old password"


@pytest.mark.asyncio
async def test_get_me_direct():
    """get_me maps the current user into a UserResponse (line 86)."""
    user = User(
        id=42,
        username="covme",
        email="covme@example.com",
        hashed_password="irrelevant",
        is_admin=True,
        is_active=True,
        gemini_api_key="stored-key",
    )
    result = await get_me(current_user=user)
    assert isinstance(result, UserResponse)
    assert result.id == 42
    assert result.username == "covme"
    assert result.email == "covme@example.com"
    assert result.is_admin is True
    # SECURITY (#143): the raw key is never returned — only a boolean flag.
    assert result.has_gemini_key is True
    assert not hasattr(result, "gemini_api_key")


@pytest.mark.asyncio
async def test_update_gemini_key_direct(db_session):
    """update_gemini_key persists the key and returns it (lines 133-138)."""
    user = User(
        username="covgemini",
        email="covgemini@example.com",
        hashed_password=get_password_hash("pw"),
        is_admin=False,
        is_active=True,
        gemini_api_key=None,
    )
    db_session.add(user)
    await db_session.commit()

    payload = UpdateGeminiKeyRequest(api_key="new-gemini-key")
    result = await update_gemini_key(key_data=payload, current_user=user, db=db_session)

    assert isinstance(result, UserResponse)
    # SECURITY (#143): write path confirms the key is set without echoing it back.
    assert result.has_gemini_key is True
    assert not hasattr(result, "gemini_api_key")
    await db_session.refresh(user)
    # The model attribute still round-trips the plaintext key for AI callers.
    assert user.gemini_api_key == "new-gemini-key"


@pytest.mark.asyncio
async def test_get_me_no_key_reports_false():
    """has_gemini_key is False when the user has no key configured (#143)."""
    user = User(
        id=7,
        username="covnokey",
        email="covnokey@example.com",
        hashed_password="irrelevant",
        is_admin=False,
        is_active=True,
        gemini_api_key=None,
    )
    result = await get_me(current_user=user)
    assert result.has_gemini_key is False


@pytest.mark.asyncio
async def test_clear_gemini_key_reports_false(db_session):
    """Clearing the key (api_key=None) reports has_gemini_key False (#143)."""
    user = User(
        username="covclear",
        email="covclear@example.com",
        hashed_password=get_password_hash("pw"),
        is_admin=False,
        is_active=True,
        gemini_api_key="some-existing-key",
    )
    db_session.add(user)
    await db_session.commit()

    result = await update_gemini_key(
        key_data=UpdateGeminiKeyRequest(api_key=None),
        current_user=user,
        db=db_session,
    )
    assert result.has_gemini_key is False
    await db_session.refresh(user)
    assert user.gemini_api_key is None
