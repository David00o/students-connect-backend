import re
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.profile import ProfileVisibility


# ── Helpers ───────────────────────────────────────────────────────────────────

# Must match the DB check constraint: ck_profiles_username_format
# ^[a-zA-Z0-9_.]{3,50}$
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.]{3,50}$")


def validate_username_format(v: str) -> str:
    if not USERNAME_REGEX.match(v):
        raise ValueError(
            "Username must be 3–50 characters and contain only letters, "
            "numbers, underscores, or dots."
        )
    return v.lower()  # normalise to lowercase — matches lower(username) index


# ── Annotated string types ────────────────────────────────────────────────────
# StringConstraints is the correct Pydantic v2 way to combine strip_whitespace
# with length constraints. Field(..., strip_whitespace=True) is a deprecated v1
# pattern that is silently ignored in v2 (stripped value is never applied).

_Name = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=50
)]
_Username = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=3, max_length=50
)]
_OptionalText = Annotated[str | None, StringConstraints(strip_whitespace=True)]
_OptionalCollege = Annotated[str | None, StringConstraints(
    strip_whitespace=True, max_length=255
)]
_OptionalBranch = Annotated[str | None, StringConstraints(
    strip_whitespace=True, max_length=100
)]


# ── Request schemas ───────────────────────────────────────────────────────────

class ProfileCreateRequest(BaseModel):
    # Required
    username: _Username
    first_name: _Name
    last_name: _Name

    # Optional — personal
    profile_photo: str | None = Field(None, max_length=500)
    cover_photo: str | None = Field(None, max_length=500)
    date_of_birth: date | None = None
    bio: _OptionalText = None
    about: _OptionalText = None

    # Optional — academic
    college: _OptionalCollege = None
    branch: _OptionalBranch = None
    academic_year: int | None = None

    # Optional — privacy
    profile_visibility: ProfileVisibility = ProfileVisibility.PUBLIC

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        return validate_username_format(v)

    @field_validator("first_name", "last_name")
    @classmethod
    def names_must_be_alpha(cls, v: str) -> str:
        if not v.replace(" ", "").replace("-", "").isalpha():
            raise ValueError("Names must contain only letters, spaces, or hyphens")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_must_be_past(cls, v: date | None) -> date | None:
        if v is not None and v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v

    @field_validator("academic_year")
    @classmethod
    def academic_year_range(cls, v: int | None) -> int | None:
        # Must match DB check constraint: ck_profiles_academic_year_range (1–8)
        if v is not None and not (1 <= v <= 8):
            raise ValueError("Academic year must be between 1 and 8")
        return v


class ProfileUpdateRequest(BaseModel):
    """
    All fields optional — supports partial (PATCH-style) updates.
    Only fields explicitly provided are written; None means 'clear this field'
    for nullable columns. The service layer distinguishes absent keys from
    explicit None using model_fields_set.
    """
    first_name: _Name | None = None
    last_name: _Name | None = None
    profile_photo: str | None = Field(None, max_length=500)
    cover_photo: str | None = Field(None, max_length=500)
    date_of_birth: date | None = None
    bio: _OptionalText = None
    about: _OptionalText = None
    college: _OptionalCollege = None
    branch: _OptionalBranch = None
    academic_year: int | None = None
    profile_visibility: ProfileVisibility | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def names_must_be_alpha(cls, v: str | None) -> str | None:
        if v is not None and not v.replace(" ", "").replace("-", "").isalpha():
            raise ValueError("Names must contain only letters, spaces, or hyphens")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_must_be_past(cls, v: date | None) -> date | None:
        if v is not None and v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v

    @field_validator("academic_year")
    @classmethod
    def academic_year_range(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 8):
            raise ValueError("Academic year must be between 1 and 8")
        return v


# ── Response schemas ──────────────────────────────────────────────────────────

class _ProfileResponseBase(BaseModel):
    """
    Shared fields present in both owner and public profile responses.
    Not intended to be used directly as an API response type.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    first_name: str
    last_name: str
    profile_photo: str | None
    cover_photo: str | None
    bio: str | None
    about: str | None
    college: str | None
    branch: str | None
    academic_year: int | None
    profile_visibility: ProfileVisibility
    created_at: datetime


class ProfileResponse(_ProfileResponseBase):
    """
    Full profile returned to the authenticated owner.
    Includes all fields — date_of_birth, profile_score, and updated_at
    are visible only to the owner.
    """
    user_id: UUID
    date_of_birth: date | None
    profile_score: int
    updated_at: datetime


class PublicProfileResponse(_ProfileResponseBase):
    """
    Subset of profile fields visible to other users.
    Excludes: user_id (internal), date_of_birth (private), profile_score
    (internal metric), updated_at (not relevant to visitors).
    profile_visibility is included — the client needs it to render
    appropriate UI (e.g. a 'connections only' banner).
    The service layer is responsible for enforcing visibility rules
    (public / connections / private) before returning this schema.
    """
    pass