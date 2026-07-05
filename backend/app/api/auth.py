from datetime import timedelta
from collections import defaultdict
import time as _time
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import (
    verify_password,
    create_access_token,
    get_current_user,
)
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── In-memory sliding-window rate limiter for /login ────────────────────────
# Tracks (ip → list of attempt timestamps). Thread-safe via a simple lock.
_login_attempts: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()
_MAX_ATTEMPTS = 10        # max login attempts
_WINDOW_SECONDS = 60      # within this sliding window (seconds)


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if the IP has exceeded the login rate limit."""
    now = _time.monotonic()
    with _rate_lock:
        attempts = _login_attempts[ip]
        # Drop attempts outside the window
        _login_attempts[ip] = [t for t in attempts if now - t < _WINDOW_SECONDS]
        if len(_login_attempts[ip]) >= _MAX_ATTEMPTS:
            logger.warning(f"Login rate limit exceeded for IP={ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Try again in {_WINDOW_SECONDS} seconds.",
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )
        _login_attempts[ip].append(now)


def _clear_rate_limit(ip: str) -> None:
    """Clear rate-limit counter on successful login."""
    with _rate_lock:
        _login_attempts.pop(ip, None)


# ── Schema ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Login endpoint that accepts username and password.
    Returns JWT access token on success.
    Rate-limited to 10 attempts per 60 seconds per IP.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Find user by username
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Successful login — clear rate limit counter
    _clear_rate_limit(client_ip)
    logger.info(f"Successful login for username={user.username} from IP={client_ip}")

    # Create access token
    access_token_expires = timedelta(minutes=settings.jwt_expiration_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "admin": user.is_admin},
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60,  # Convert to seconds
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
    )


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    # Verify old password
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect old password"
        )

    # Update password
    from app.services.auth import get_password_hash

    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.add(current_user)
    await db.commit()
    return
