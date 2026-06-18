from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    APIResponse,
    AccessTokenResponse,
    ChangePasswordRequest,
    CreatePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    PasswordResetTokenResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    VerifyOTPRequest,
    VerifyResetOTPRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


# ── 1. Signup ─────────────────────────────────────────────────────────────────

@router.post(
    "/signup",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Create account — sends email OTP",
)
async def signup(
    payload: SignupRequest,
    service: AuthService = Depends(_get_service),
) -> APIResponse:
    result = await service.signup(payload)
    return APIResponse(**result)


# ── 2. Verify OTP ─────────────────────────────────────────────────────────────

@router.post(
    "/verify-otp",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email OTP",
)
async def verify_otp(
    payload: VerifyOTPRequest,
    service: AuthService = Depends(_get_service),
) -> APIResponse:
    result = await service.verify_otp(payload)
    return APIResponse(**result)


# ── 3. Create password ────────────────────────────────────────────────────────

@router.post(
    "/create-password",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set password after OTP verification — returns JWT",
)
async def create_password(
    payload: CreatePasswordRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    return await service.create_password(payload)


# ── 4. Login ──────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email/phone and password",
)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    return await service.login(payload)


# ── 5. Refresh token ──────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange refresh token for a new access token",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(_get_service),
) -> AccessTokenResponse:
    result = await service.refresh_token(payload)
    return AccessTokenResponse(**result)


# ── 6. Logout ─────────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout (invalidate token client-side)",
)
async def logout(
    service: AuthService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> APIResponse:
    result = await service.logout(current_user)
    return APIResponse(**result)


# ── 7. Forgot password ────────────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset OTP via email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(_get_service),
) -> APIResponse:
    result = await service.forgot_password(payload)
    return APIResponse(**result)


# ── 8. Verify reset OTP ───────────────────────────────────────────────────────

@router.post(
    "/verify-reset-otp",
    response_model=PasswordResetTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify password reset OTP — returns a signed reset token",
)
async def verify_reset_otp(
    payload: VerifyResetOTPRequest,
    service: AuthService = Depends(_get_service),
) -> PasswordResetTokenResponse:
    return await service.verify_reset_otp(payload)


# ── 9. Reset password ─────────────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password using the reset token from verify-reset-otp",
)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(_get_service),
) -> APIResponse:
    result = await service.reset_password(payload)
    return APIResponse(**result)


# ── 10. Change password ───────────────────────────────────────────────────────

@router.put(
    "/change-password",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password (requires login)",
)
async def change_password(
    payload: ChangePasswordRequest,
    service: AuthService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> APIResponse:
    result = await service.change_password(payload, current_user)
    return APIResponse(**result)