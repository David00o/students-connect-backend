import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Helpers ───────────────────────────────────────────────────────────────────

PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
)


def validate_password_strength(v: str) -> str:
    if not PASSWORD_REGEX.match(v):
        raise ValueError(
            "Password must be at least 8 characters and include uppercase, "
            "lowercase, digit, and special character (@$!%*?&)."
        )
    return v


# ── Standard API envelope ─────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None


# ── Request schemas ───────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50, strip_whitespace=True)
    last_name: str = Field(..., min_length=1, max_length=50, strip_whitespace=True)
    date_of_birth: date
    email: EmailStr

    @field_validator("date_of_birth")
    @classmethod
    def dob_must_be_past(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def names_must_be_alpha(cls, v: str) -> str:
        if not v.replace(" ", "").replace("-", "").isalpha():
            raise ValueError("Names must contain only letters, spaces, or hyphens")
        return v


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class CreatePasswordRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "CreatePasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email_or_phone: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    """
    Password reset using the signed reset token returned by verify-reset-otp.
    The OTP is not included here — it was already consumed in the previous step.
    """
    reset_token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


# ── Response schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: UUID
    email: str
    phone_number: str | None
    email_verified: bool
    account_status: str
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    success: bool = True
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class AccessTokenResponse(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = "bearer"


class PasswordResetTokenResponse(BaseModel):
    """Returned by verify-reset-otp. Client passes reset_token to reset-password."""
    success: bool = True
    message: str
    reset_token: str