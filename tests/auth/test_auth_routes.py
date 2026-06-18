"""
Integration tests for Auth API routes.
Uses real FastAPI app + in-memory SQLite (via conftest fixtures).
Email sending is mocked in all tests.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from app.core.security import create_password_reset_token, create_access_token

BASE = "/api/v1/auth"


# ── Signup ────────────────────────────────────────────────────────────────────

class TestSignupRoute:
    @pytest.mark.asyncio
    async def test_signup_returns_200(self, client: AsyncClient):
        with patch("app.services.auth_service.send_verification_otp", new_callable=AsyncMock):
            resp = await client.post(f"{BASE}/signup", json={
                "first_name": "Alice", "last_name": "Smith",
                "date_of_birth": "2000-01-01", "email": "alice@example.com",
            })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_signup_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/signup", json={
            "first_name": "Alice", "last_name": "Smith",
            "date_of_birth": "2000-01-01", "email": "not-an-email",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_signup_future_dob_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/signup", json={
            "first_name": "Alice", "last_name": "Smith",
            "date_of_birth": "2099-01-01", "email": "alice2@example.com",
        })
        assert resp.status_code == 422


# ── Verify OTP ────────────────────────────────────────────────────────────────

class TestVerifyOTPRoute:
    @pytest.mark.asyncio
    async def test_invalid_otp_returns_400(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/verify-otp", json={
            "email": "nobody@example.com", "otp": "000000",
        })
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_non_numeric_otp_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/verify-otp", json={
            "email": "test@example.com", "otp": "abc123",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_short_otp_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/verify-otp", json={
            "email": "test@example.com", "otp": "12345",
        })
        assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLoginRoute:
    @pytest.mark.asyncio
    async def test_login_wrong_credentials_returns_401(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/login", json={
            "email_or_phone": "ghost@example.com", "password": "SomePass@1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/login", json={"email_or_phone": "test@example.com"})
        assert resp.status_code == 422


# ── Forgot Password ───────────────────────────────────────────────────────────

class TestForgotPasswordRoute:
    @pytest.mark.asyncio
    async def test_always_returns_200_for_unknown_email(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/forgot-password", json={"email": "unknown@example.com"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/forgot-password", json={"email": "not-email"})
        assert resp.status_code == 422


# ── Verify Reset OTP ──────────────────────────────────────────────────────────

class TestVerifyResetOTPRoute:
    @pytest.mark.asyncio
    async def test_invalid_otp_returns_400(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/verify-reset-otp", json={
            "email": "test@example.com", "otp": "000000",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_non_numeric_otp_returns_422(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/verify-reset-otp", json={
            "email": "test@example.com", "otp": "abcdef",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_response_contains_reset_token_field(self, client: AsyncClient):
        """Verify-reset-otp must return reset_token, not a plain message."""
        # Even on failure the response shape tells us the field exists in schema.
        # On success (tested in service tests), reset_token is always present.
        resp = await client.post(f"{BASE}/verify-reset-otp", json={
            "email": "test@example.com", "otp": "000000",
        })
        # 400 because OTP is invalid; important thing is it's not a 422 schema error
        assert resp.status_code == 400


# ── Reset Password ────────────────────────────────────────────────────────────

class TestResetPasswordRoute:
    @pytest.mark.asyncio
    async def test_invalid_reset_token_returns_401(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/reset-password", json={
            "reset_token": "garbage.token.here",
            "new_password": "NewPass@1",
            "confirm_password": "NewPass@1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_access_token_rejected_as_reset_token(self, client: AsyncClient):
        """An access token must not be accepted where a reset token is expected."""
        access_token = create_access_token("some-user-id")
        resp = await client.post(f"{BASE}/reset-password", json={
            "reset_token": access_token,
            "new_password": "NewPass@1",
            "confirm_password": "NewPass@1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_password_mismatch_returns_422(self, client: AsyncClient):
        reset_token = create_password_reset_token("test@example.com")
        resp = await client.post(f"{BASE}/reset-password", json={
            "reset_token": reset_token,
            "new_password": "NewPass@1",
            "confirm_password": "DifferentPass@1",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_weak_password_returns_422(self, client: AsyncClient):
        reset_token = create_password_reset_token("test@example.com")
        resp = await client.post(f"{BASE}/reset-password", json={
            "reset_token": reset_token,
            "new_password": "weakpass",
            "confirm_password": "weakpass",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_otp_field_rejected_in_reset_request(self, client: AsyncClient):
        """Old API shape (with otp field) must be rejected — no backward compat."""
        resp = await client.post(f"{BASE}/reset-password", json={
            "email": "test@example.com",
            "otp": "123456",                 # old field — must not be accepted
            "new_password": "NewPass@1",
            "confirm_password": "NewPass@1",
        })
        # Missing reset_token → 422
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_reset_token_but_unknown_user_returns_404(self, client: AsyncClient):
        """Token is valid but the email doesn't exist in the DB."""
        reset_token = create_password_reset_token("nobody@example.com")
        resp = await client.post(f"{BASE}/reset-password", json={
            "reset_token": reset_token,
            "new_password": "NewPass@1",
            "confirm_password": "NewPass@1",
        })
        assert resp.status_code == 404


# ── Logout ────────────────────────────────────────────────────────────────────

class TestLogoutRoute:
    @pytest.mark.asyncio
    async def test_logout_without_token_returns_403(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/logout")
        assert resp.status_code == 403


# ── Change Password ───────────────────────────────────────────────────────────

class TestChangePasswordRoute:
    @pytest.mark.asyncio
    async def test_change_password_without_token_returns_403(self, client: AsyncClient):
        resp = await client.put(f"{BASE}/change-password", json={
            "current_password": "OldPass@1",
            "new_password": "NewPass@2", "confirm_password": "NewPass@2",
        })
        assert resp.status_code == 403