import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_password_reset_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.otp import OTPPurpose
from app.models.user import User
from app.repositories.otp_repository import OTPRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    CreatePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    PasswordResetTokenResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    VerifyOTPRequest,
    VerifyResetOTPRequest,
)
from app.utils.email import send_password_reset_otp, send_verification_otp
from app.utils.otp import generate_otp

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._user_repo = UserRepository(db)
        self._otp_repo = OTPRepository(db)

    # ── 1. Signup ─────────────────────────────────────────────────────────────

    async def signup(self, payload: SignupRequest) -> dict:
        existing = await self._user_repo.get_by_email(payload.email)

        if existing:
            if existing.email_verified:
                raise ConflictException("An account with this email already exists.")
            user = existing
        else:
            user = await self._user_repo.create(
                email=payload.email,
                first_name=payload.first_name,
                last_name=payload.last_name,
                date_of_birth=payload.date_of_birth,
            )

        otp_code = generate_otp()
        await self._otp_repo.create(
            email=user.email,
            otp_code=otp_code,
            purpose=OTPPurpose.EMAIL_VERIFICATION,
        )
        await send_verification_otp(to=user.email, otp_code=otp_code)
        logger.info("Signup OTP sent to %s", user.email)

        return {"success": True, "message": "OTP sent successfully"}

    # ── 2. Verify OTP ─────────────────────────────────────────────────────────

    async def verify_otp(self, payload: VerifyOTPRequest) -> dict:
        otp = await self._otp_repo.get_valid(
            email=payload.email,
            otp_code=payload.otp,
            purpose=OTPPurpose.EMAIL_VERIFICATION,
        )
        if otp is None:
            raise BadRequestException("Invalid or expired OTP.")

        await self._otp_repo.mark_used(otp)
        return {"success": True, "message": "OTP verified"}

    # ── 3. Create password ────────────────────────────────────────────────────

    async def create_password(self, payload: CreatePasswordRequest) -> TokenResponse:
        user = await self._user_repo.get_by_email(payload.email)
        if user is None:
            raise NotFoundException("User not found.")

        if user.password_hash is not None:
            raise ConflictException("Password has already been set. Please login.")

        pw_hash = hash_password(payload.password)
        await self._user_repo.set_password(user, pw_hash)
        await self._user_repo.update_last_login(user)

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    # ── 4. Login ──────────────────────────────────────────────────────────────

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self._user_repo.get_by_email_or_phone(payload.email_or_phone)

        if user is None or user.password_hash is None:
            raise UnauthorizedException("Invalid credentials.")

        if not verify_password(payload.password, user.password_hash):
            raise UnauthorizedException("Invalid credentials.")

        if not user.email_verified:
            raise BadRequestException(
                "Email not verified. Please complete registration."
            )

        await self._user_repo.update_last_login(user)

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        logger.info("User %s logged in", user.email)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    # ── 5. Refresh token ──────────────────────────────────────────────────────

    async def refresh_token(self, payload: RefreshTokenRequest) -> dict:
        user_id = decode_refresh_token(payload.refresh_token)
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise UnauthorizedException("User not found.")

        new_access_token = create_access_token(str(user.id))
        return {
            "success": True,
            "access_token": new_access_token,
            "token_type": "bearer",
        }

    # ── 6. Logout ─────────────────────────────────────────────────────────────

    async def logout(self, current_user: User) -> dict:
        logger.info("User %s logged out", current_user.email)
        return {"success": True, "message": "Logged out successfully"}

    # ── 7. Forgot password ────────────────────────────────────────────────────

    async def forgot_password(self, payload: ForgotPasswordRequest) -> dict:
        user = await self._user_repo.get_by_email(payload.email)

        # Always return the same message to prevent email enumeration
        if user is None or not user.email_verified:
            return {"success": True, "message": "If the email exists, an OTP has been sent."}

        otp_code = generate_otp()
        await self._otp_repo.create(
            email=user.email,
            otp_code=otp_code,
            purpose=OTPPurpose.PASSWORD_RESET,
        )
        await send_password_reset_otp(to=user.email, otp_code=otp_code)
        logger.info("Password reset OTP sent to %s", user.email)

        return {"success": True, "message": "If the email exists, an OTP has been sent."}

    # ── 8. Verify reset OTP ───────────────────────────────────────────────────

    async def verify_reset_otp(self, payload: VerifyResetOTPRequest) -> PasswordResetTokenResponse:
        """
        Validate the OTP and immediately consume it (mark used).
        On success, issue a short-lived signed password reset token (15 min TTL).
        The client passes this token — not the OTP — to reset-password.

        This design prevents OTP reuse and eliminates the race condition where
        the same OTP was previously required in both verify-reset-otp AND
        reset-password, causing the second call to always fail because
        get_valid() only returns unused OTPs.
        """
        otp = await self._otp_repo.get_valid(
            email=payload.email,
            otp_code=payload.otp,
            purpose=OTPPurpose.PASSWORD_RESET,
        )
        if otp is None:
            raise BadRequestException("Invalid or expired OTP.")

        # Consume the OTP immediately — it is now worthless
        await self._otp_repo.mark_used(otp)

        # Issue a scoped, short-lived reset token
        reset_token = create_password_reset_token(payload.email)
        logger.info("Password reset OTP verified for %s", payload.email)

        return PasswordResetTokenResponse(
            success=True,
            message="OTP verified. Use the reset_token to set your new password.",
            reset_token=reset_token,
        )

    # ── 9. Reset password ─────────────────────────────────────────────────────

    async def reset_password(self, payload: ResetPasswordRequest) -> dict:
        """
        Reset the password using the signed reset token from verify-reset-otp.
        No OTP involvement here — the token is the proof of identity.
        """
        # decode_password_reset_token raises UnauthorizedException on any failure
        email = decode_password_reset_token(payload.reset_token)

        user = await self._user_repo.get_by_email(email)
        if user is None:
            raise NotFoundException("User not found.")

        pw_hash = hash_password(payload.new_password)
        await self._user_repo.update_password(user, pw_hash)

        logger.info("Password reset for %s", email)
        return {"success": True, "message": "Password reset successfully. Please login."}

    # ── 10. Change password ───────────────────────────────────────────────────

    async def change_password(
        self, payload: ChangePasswordRequest, current_user: User
    ) -> dict:
        if current_user.password_hash is None:
            raise BadRequestException("No password set for this account.")

        if not verify_password(payload.current_password, current_user.password_hash):
            raise UnauthorizedException("Current password is incorrect.")

        if payload.current_password == payload.new_password:
            raise BadRequestException("New password must differ from the current password.")

        pw_hash = hash_password(payload.new_password)
        await self._user_repo.update_password(current_user, pw_hash)

        logger.info("Password changed for %s", current_user.email)
        return {"success": True, "message": "Password changed successfully."}