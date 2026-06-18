"""
Unit tests for AuthService.
All external dependencies (DB repos, email) are mocked.
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import date, datetime, timezone, timedelta
import uuid

from app.services.auth_service import AuthService
from app.schemas.auth import (
    SignupRequest,
    VerifyOTPRequest,
    CreatePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    VerifyResetOTPRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.security import create_password_reset_token
from app.models.user import AccountStatus, User
from app.models.otp import OTP, OTPPurpose


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(
    email: str = "test@example.com",
    password_hash: str | None = None,
    email_verified: bool = False,
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = email
    u.password_hash = password_hash
    u.email_verified = email_verified
    u.account_status = account_status
    u.phone_number = None
    u.last_login_at = None
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def make_otp(
    email: str = "test@example.com",
    otp_code: str = "123456",
    purpose: OTPPurpose = OTPPurpose.EMAIL_VERIFICATION,
    is_used: bool = False,
) -> OTP:
    o = OTP()
    o.id = uuid.uuid4()
    o.email = email
    o.otp_code = otp_code
    o.purpose = purpose
    o.is_used = is_used
    o.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    return o


def make_service() -> AuthService:
    return AuthService(AsyncMock())


# ── Signup ────────────────────────────────────────────────────────────────────

class TestSignup:
    @pytest.mark.asyncio
    async def test_new_user_sends_otp(self):
        service = make_service()
        payload = SignupRequest(
            first_name="Alice", last_name="Smith",
            date_of_birth=date(2000, 1, 1), email="alice@example.com",
        )
        service._user_repo.get_by_email = AsyncMock(return_value=None)
        service._user_repo.create = AsyncMock(return_value=make_user(email="alice@example.com"))
        service._otp_repo.create = AsyncMock(return_value=make_otp())

        with patch("app.services.auth_service.send_verification_otp", new_callable=AsyncMock):
            result = await service.signup(payload)

        assert result["success"] is True
        service._user_repo.create.assert_awaited_once()
        service._otp_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_existing_verified_email_raises_conflict(self):
        service = make_service()
        payload = SignupRequest(
            first_name="Alice", last_name="Smith",
            date_of_birth=date(2000, 1, 1), email="alice@example.com",
        )
        service._user_repo.get_by_email = AsyncMock(return_value=make_user(email_verified=True))

        with pytest.raises(ConflictException):
            await service.signup(payload)

    @pytest.mark.asyncio
    async def test_unverified_existing_user_resends_otp(self):
        service = make_service()
        existing = make_user(email_verified=False)
        payload = SignupRequest(
            first_name="Alice", last_name="Smith",
            date_of_birth=date(2000, 1, 1), email="alice@example.com",
        )
        service._user_repo.get_by_email = AsyncMock(return_value=existing)
        service._otp_repo.create = AsyncMock(return_value=make_otp())
        service._user_repo.create = AsyncMock()

        with patch("app.services.auth_service.send_verification_otp", new_callable=AsyncMock):
            result = await service.signup(payload)

        assert result["success"] is True
        service._user_repo.create.assert_not_called()


# ── Verify OTP ────────────────────────────────────────────────────────────────

class TestVerifyOTP:
    @pytest.mark.asyncio
    async def test_valid_otp_is_marked_used(self):
        service = make_service()
        otp = make_otp()
        service._otp_repo.get_valid = AsyncMock(return_value=otp)
        service._otp_repo.mark_used = AsyncMock()

        result = await service.verify_otp(VerifyOTPRequest(email="test@example.com", otp="123456"))

        assert result["success"] is True
        service._otp_repo.mark_used.assert_awaited_once_with(otp)

    @pytest.mark.asyncio
    async def test_invalid_otp_raises_bad_request(self):
        service = make_service()
        service._otp_repo.get_valid = AsyncMock(return_value=None)

        with pytest.raises(BadRequestException):
            await service.verify_otp(VerifyOTPRequest(email="test@example.com", otp="000000"))


# ── Create Password ───────────────────────────────────────────────────────────

class TestCreatePassword:
    @pytest.mark.asyncio
    async def test_sets_password_and_returns_tokens(self):
        service = make_service()
        user = make_user(email_verified=False, password_hash=None)
        service._user_repo.get_by_email = AsyncMock(return_value=user)
        service._user_repo.set_password = AsyncMock(return_value=user)
        service._user_repo.update_last_login = AsyncMock()

        result = await service.create_password(CreatePasswordRequest(
            email="test@example.com",
            password="StrongPass@1", confirm_password="StrongPass@1",
        ))

        assert result.access_token
        assert result.refresh_token
        service._user_repo.set_password.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_not_found_raises_404(self):
        service = make_service()
        service._user_repo.get_by_email = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.create_password(CreatePasswordRequest(
                email="ghost@example.com",
                password="StrongPass@1", confirm_password="StrongPass@1",
            ))

    @pytest.mark.asyncio
    async def test_password_already_set_raises_conflict(self):
        service = make_service()
        service._user_repo.get_by_email = AsyncMock(return_value=make_user(password_hash="hashed"))

        with pytest.raises(ConflictException):
            await service.create_password(CreatePasswordRequest(
                email="test@example.com",
                password="StrongPass@1", confirm_password="StrongPass@1",
            ))


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    @pytest.mark.asyncio
    async def test_valid_credentials_returns_tokens(self):
        service = make_service()
        user = make_user(email_verified=True)
        user.password_hash = "$2b$12$fakehashedpassword"
        service._user_repo.get_by_email_or_phone = AsyncMock(return_value=user)
        service._user_repo.update_last_login = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            result = await service.login(LoginRequest(
                email_or_phone="test@example.com", password="anypassword"
            ))

        assert result.access_token
        assert result.refresh_token

    @pytest.mark.asyncio
    async def test_wrong_password_raises_unauthorized(self):
        service = make_service()
        user = make_user(email_verified=True)
        user.password_hash = "$2b$12$fakehashedpassword"
        service._user_repo.get_by_email_or_phone = AsyncMock(return_value=user)

        with patch("app.services.auth_service.verify_password", return_value=False):
            with pytest.raises(UnauthorizedException):
                await service.login(LoginRequest(
                    email_or_phone="test@example.com", password="wrongpass"
                ))

    @pytest.mark.asyncio
    async def test_unverified_email_raises_bad_request(self):
        service = make_service()
        user = make_user(email_verified=False)
        user.password_hash = "$2b$12$fakehashedpassword"
        service._user_repo.get_by_email_or_phone = AsyncMock(return_value=user)

        with patch("app.services.auth_service.verify_password", return_value=True):
            with pytest.raises(BadRequestException):
                await service.login(LoginRequest(
                    email_or_phone="test@example.com", password="anypassword"
                ))

    @pytest.mark.asyncio
    async def test_user_not_found_raises_unauthorized(self):
        service = make_service()
        service._user_repo.get_by_email_or_phone = AsyncMock(return_value=None)

        with pytest.raises(UnauthorizedException):
            await service.login(LoginRequest(
                email_or_phone="nobody@example.com", password="pass"
            ))


# ── Refresh Token ─────────────────────────────────────────────────────────────

class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_valid_refresh_token_returns_new_access_token(self):
        service = make_service()
        user = make_user()
        service._user_repo.get_by_id = AsyncMock(return_value=user)

        with patch("app.services.auth_service.decode_refresh_token", return_value=str(user.id)):
            result = await service.refresh_token(RefreshTokenRequest(refresh_token="dummy"))

        assert result["success"] is True
        assert "access_token" in result

    @pytest.mark.asyncio
    async def test_user_not_found_raises_unauthorized(self):
        service = make_service()
        service._user_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.services.auth_service.decode_refresh_token", return_value=str(uuid.uuid4())):
            with pytest.raises(UnauthorizedException):
                await service.refresh_token(RefreshTokenRequest(refresh_token="dummy"))


# ── Forgot Password ───────────────────────────────────────────────────────────

class TestForgotPassword:
    @pytest.mark.asyncio
    async def test_sends_otp_to_verified_email(self):
        service = make_service()
        user = make_user(email_verified=True)
        service._user_repo.get_by_email = AsyncMock(return_value=user)
        service._otp_repo.create = AsyncMock(
            return_value=make_otp(purpose=OTPPurpose.PASSWORD_RESET)
        )

        with patch("app.services.auth_service.send_password_reset_otp", new_callable=AsyncMock):
            result = await service.forgot_password(ForgotPasswordRequest(email="test@example.com"))

        assert result["success"] is True
        service._otp_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_nonexistent_email_still_returns_success(self):
        service = make_service()
        service._user_repo.get_by_email = AsyncMock(return_value=None)

        result = await service.forgot_password(ForgotPasswordRequest(email="ghost@example.com"))

        assert result["success"] is True


# ── Verify Reset OTP ──────────────────────────────────────────────────────────

class TestVerifyResetOTP:
    @pytest.mark.asyncio
    async def test_valid_otp_returns_reset_token(self):
        service = make_service()
        otp = make_otp(purpose=OTPPurpose.PASSWORD_RESET)
        service._otp_repo.get_valid = AsyncMock(return_value=otp)
        service._otp_repo.mark_used = AsyncMock()

        result = await service.verify_reset_otp(
            VerifyResetOTPRequest(email="test@example.com", otp="123456")
        )

        assert result.success is True
        assert result.reset_token  # a JWT was returned
        service._otp_repo.mark_used.assert_awaited_once_with(otp)

    @pytest.mark.asyncio
    async def test_otp_is_consumed_immediately(self):
        """OTP must be marked used during verify — not deferred to reset-password."""
        service = make_service()
        otp = make_otp(purpose=OTPPurpose.PASSWORD_RESET)
        service._otp_repo.get_valid = AsyncMock(return_value=otp)
        service._otp_repo.mark_used = AsyncMock()

        await service.verify_reset_otp(
            VerifyResetOTPRequest(email="test@example.com", otp="123456")
        )

        service._otp_repo.mark_used.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_otp_raises_bad_request(self):
        service = make_service()
        service._otp_repo.get_valid = AsyncMock(return_value=None)

        with pytest.raises(BadRequestException):
            await service.verify_reset_otp(
                VerifyResetOTPRequest(email="test@example.com", otp="000000")
            )

    @pytest.mark.asyncio
    async def test_reset_token_is_scoped_to_password_reset(self):
        """Reset token must not be accepted as an access token."""
        from app.core.security import decode_access_token, decode_password_reset_token

        service = make_service()
        otp = make_otp(purpose=OTPPurpose.PASSWORD_RESET)
        service._otp_repo.get_valid = AsyncMock(return_value=otp)
        service._otp_repo.mark_used = AsyncMock()

        result = await service.verify_reset_otp(
            VerifyResetOTPRequest(email="test@example.com", otp="123456")
        )

        # Must decode correctly as reset token
        email = decode_password_reset_token(result.reset_token)
        assert email == "test@example.com"

        # Must NOT be accepted as an access token
        with pytest.raises(UnauthorizedException):
            decode_access_token(result.reset_token)


# ── Reset Password ────────────────────────────────────────────────────────────

class TestResetPassword:
    @pytest.mark.asyncio
    async def test_valid_reset_token_resets_password(self):
        service = make_service()
        user = make_user(email="test@example.com", email_verified=True)
        service._user_repo.get_by_email = AsyncMock(return_value=user)
        service._user_repo.update_password = AsyncMock()

        # Issue a real reset token
        reset_token = create_password_reset_token("test@example.com")

        result = await service.reset_password(ResetPasswordRequest(
            reset_token=reset_token,
            new_password="NewPass@1",
            confirm_password="NewPass@1",
        ))

        assert result["success"] is True
        service._user_repo.update_password.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_reset_token_raises_unauthorized(self):
        service = make_service()

        with pytest.raises(UnauthorizedException):
            await service.reset_password(ResetPasswordRequest(
                reset_token="this.is.garbage",
                new_password="NewPass@1",
                confirm_password="NewPass@1",
            ))

    @pytest.mark.asyncio
    async def test_access_token_rejected_as_reset_token(self):
        """An access token must not be accepted in place of a reset token."""
        from app.core.security import create_access_token
        service = make_service()

        access_token = create_access_token("some-user-id")

        with pytest.raises(UnauthorizedException):
            await service.reset_password(ResetPasswordRequest(
                reset_token=access_token,
                new_password="NewPass@1",
                confirm_password="NewPass@1",
            ))

    @pytest.mark.asyncio
    async def test_user_not_found_raises_404(self):
        service = make_service()
        service._user_repo.get_by_email = AsyncMock(return_value=None)
        reset_token = create_password_reset_token("ghost@example.com")

        with pytest.raises(NotFoundException):
            await service.reset_password(ResetPasswordRequest(
                reset_token=reset_token,
                new_password="NewPass@1",
                confirm_password="NewPass@1",
            ))

    def test_no_otp_field_in_reset_request(self):
        """
        Confirm ResetPasswordRequest no longer has an otp field.
        Pydantic silently ignores unknown fields, so the correct assertion
        is that the constructed object does NOT have an otp attribute,
        and that reset_token IS required.
        """
        import pydantic
        # reset_token is required — omitting it raises ValidationError
        with pytest.raises(pydantic.ValidationError):
            ResetPasswordRequest(
                new_password="NewPass@1",
                confirm_password="NewPass@1",
            )

        # otp is silently ignored — the object is valid but has no otp attribute
        req = ResetPasswordRequest(
            otp="123456",
            reset_token="sometoken",
            new_password="NewPass@1",
            confirm_password="NewPass@1",
        )
        assert not hasattr(req, "otp"), "otp must not be a field on ResetPasswordRequest"
        assert req.reset_token == "sometoken"


# ── Change Password ───────────────────────────────────────────────────────────

class TestChangePassword:
    @pytest.mark.asyncio
    async def test_correct_current_password_changes_it(self):
        service = make_service()
        user = make_user()
        user.password_hash = "$2b$12$fakehashedpassword"
        service._user_repo.update_password = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            result = await service.change_password(
                ChangePasswordRequest(
                    current_password="OldPass@1",
                    new_password="NewPass@2", confirm_password="NewPass@2",
                ),
                user,
            )

        assert result["success"] is True
        service._user_repo.update_password.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wrong_current_password_raises_unauthorized(self):
        service = make_service()
        user = make_user()
        user.password_hash = "$2b$12$fakehashedpassword"

        with patch("app.services.auth_service.verify_password", return_value=False):
            with pytest.raises(UnauthorizedException):
                await service.change_password(
                    ChangePasswordRequest(
                        current_password="WrongPass@1",
                        new_password="NewPass@2", confirm_password="NewPass@2",
                    ),
                    user,
                )

    @pytest.mark.asyncio
    async def test_same_password_raises_bad_request(self):
        service = make_service()
        user = make_user()
        user.password_hash = "$2b$12$fakehashedpassword"

        with patch("app.services.auth_service.verify_password", return_value=True):
            with pytest.raises(BadRequestException):
                await service.change_password(
                    ChangePasswordRequest(
                        current_password="SamePass@1",
                        new_password="SamePass@1", confirm_password="SamePass@1",
                    ),
                    user,
                )

    @pytest.mark.asyncio
    async def test_no_password_set_raises_bad_request(self):
        service = make_service()
        user = make_user(password_hash=None)

        with pytest.raises(BadRequestException):
            await service.change_password(
                ChangePasswordRequest(
                    current_password="OldPass@1",
                    new_password="NewPass@2", confirm_password="NewPass@2",
                ),
                user,
            )