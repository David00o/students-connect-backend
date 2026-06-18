"""
Unit tests for core security utilities.
"""
import pytest
from jose import jwt

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.core.exceptions import UnauthorizedException
from app.core.config import settings


class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        plain = "MySecret@1"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password_returns_true(self):
        plain = "MySecret@1"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_returns_false(self):
        hashed = hash_password("MySecret@1")
        assert verify_password("WrongPass@1", hashed) is False

    def test_same_password_generates_different_hashes(self):
        """bcrypt uses a random salt."""
        h1 = hash_password("MySecret@1")
        h2 = hash_password("MySecret@1")
        assert h1 != h2


class TestJWT:
    def test_access_token_contains_correct_claims(self):
        user_id = "user-uuid-1234"
        token = create_access_token(user_id)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_refresh_token_contains_correct_claims(self):
        user_id = "user-uuid-1234"
        token = create_refresh_token(user_id)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_decode_access_token_returns_user_id(self):
        user_id = "user-uuid-5678"
        token = create_access_token(user_id)
        result = decode_access_token(token)
        assert result == user_id

    def test_decode_refresh_token_returns_user_id(self):
        user_id = "user-uuid-5678"
        token = create_refresh_token(user_id)
        result = decode_refresh_token(token)
        assert result == user_id

    def test_access_token_rejected_as_refresh(self):
        """An access token must not be accepted where a refresh token is expected."""
        token = create_access_token("uid-abc")
        with pytest.raises(UnauthorizedException):
            decode_refresh_token(token)

    def test_refresh_token_rejected_as_access(self):
        """A refresh token must not be accepted where an access token is expected."""
        token = create_refresh_token("uid-abc")
        with pytest.raises(UnauthorizedException):
            decode_access_token(token)

    def test_tampered_token_raises_unauthorized(self):
        token = create_access_token("uid-xyz")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(UnauthorizedException):
            decode_access_token(tampered)

    def test_garbage_token_raises_unauthorized(self):
        with pytest.raises(UnauthorizedException):
            decode_access_token("this.is.garbage")
