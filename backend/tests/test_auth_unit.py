from datetime import timedelta
from app.services.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "secretpassword"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_access_token_creation_and_decoding():
    data = {"sub": "testuser", "admin": True}
    token = create_access_token(data)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "testuser"
    assert decoded["admin"] is True
    assert "exp" in decoded


def test_access_token_expiration():
    data = {"sub": "testuser"}
    # Create token expiring immediately
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    decoded = decode_access_token(token)
    # verify expiration logic depends on library, usually decode fails if expired?
    # jose.jwt.decode raises ExpiredSignatureError if verify_exp=True (default)
    # Our decode_access_token catches JWTError and returns None
    assert decoded is None


def test_decode_invalid_token():
    assert decode_access_token("invalid.token.string") is None
