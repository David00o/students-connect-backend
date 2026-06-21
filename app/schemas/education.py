from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

# ── Annotated string types ────────────────────────────────────────────────────
# StringConstraints is the correct Pydantic v2 way to combine strip_whitespace
# with length constraints. Field(..., strip_whitespace=True) is a deprecated v1
# pattern that is silently ignored in v2 (stripped value is never applied).
# Reused from the same pattern established in app/schemas/profile.py.

_InstitutionName = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=255
)]
_Degree = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=100
)]
_OptionalBranch = Annotated[str | None, StringConstraints(
    strip_whitespace=True, max_length=100
)]
_OptionalGrade = Annotated[str | None, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=50
)]

# Must match the DB check constraints:
#   ck_educations_start_year_range, ck_educations_end_year_range
# (start_year >= 1950 AND start_year <= 2100)
_MIN_YEAR = 1950
_MAX_YEAR = 2100


def _validate_year_range(v: int | None) -> int | None:
    if v is not None and not (_MIN_YEAR <= v <= _MAX_YEAR):
        raise ValueError(f"Year must be between {_MIN_YEAR} and {_MAX_YEAR}")
    return v


# ── Request schemas ───────────────────────────────────────────────────────────

class EducationCreateRequest(BaseModel):
    # Required
    institution_name: _InstitutionName
    degree: _Degree
    start_year: int

    # Optional
    branch: _OptionalBranch = None
    end_year: int | None = None
    currently_studying: bool = False
    grade: _OptionalGrade = None

    @field_validator("start_year")
    @classmethod
    def start_year_range(cls, v: int) -> int:
        # Must match DB check constraint: ck_educations_start_year_range
        return _validate_year_range(v)  # type: ignore[return-value]

    @field_validator("end_year")
    @classmethod
    def end_year_range(cls, v: int | None) -> int | None:
        # Must match DB check constraint: ck_educations_end_year_range
        return _validate_year_range(v)

    @model_validator(mode="after")
    def cross_field_rules(self) -> "EducationCreateRequest":
        # Must match DB check constraint: ck_educations_end_after_start
        if self.end_year is not None and self.end_year < self.start_year:
            raise ValueError("end_year cannot be earlier than start_year")
        return self


class EducationUpdateRequest(BaseModel):
    """
    All fields optional — supports partial (PATCH-style) updates.
    Only fields explicitly provided are written; None means 'clear this field'
    for nullable columns. The service layer distinguishes absent keys from
    explicit None using model_fields_set — consistent with ProfileUpdateRequest.

    Two-stage cross-field validation contract
    -------------------------------------------
    end_year is independently optional and carries no relationship to
    currently_studying — it represents the expected graduation year when
    currently_studying is true, or the actual graduation year when false.
    (Previously, end_year was forbidden while currently_studying was true;
    that rule has been removed — see
    alembic/versions/004_education_end_year_rule.py.)

    The one remaining cross-field rule — end_year cannot be earlier than
    start_year — is validated in TWO separate places, deliberately, because
    a PATCH request only ever contains a partial view of the entity:

    1. THIS SCHEMA validates the rule whenever the request itself contains
       enough information to check it — i.e. when BOTH start_year and
       end_year were sent together in the same request. This catches the
       obviously-invalid case where a client submits a single payload that
       is self-contradictory on its own terms, e.g.
       {"start_year": 2025, "end_year": 2020} — rejected right here,
       before the request ever reaches the service layer.

    2. THE SERVICE LAYER performs a second, independent validation pass
       after merging this payload with the persisted Education row. This
       is required because a partial update may legitimately touch only
       ONE side of the rule — e.g. a request containing only
       {"end_year": 2020} says nothing about start_year, so this schema
       has no way to know whether 2020 conflicts with whatever start_year
       is already stored in the database. Only the service layer has
       both the incoming payload and the current row, so only the service
       layer can validate the rule against the entity's *final* merged
       state.

    Why this matters: skipping step 2 would allow a sequence of two
    individually-valid-looking PATCH requests to leave the row in an
    invalid state that this schema alone could never detect — e.g. a
    prior request set start_year=2024, and this request sends only
    {"end_year": 2020} — the schema alone cannot see the conflict because
    start_year never appears in this request. Step 1 alone cannot catch
    this; step 2 closes the gap.
    """
    institution_name: _InstitutionName | None = None
    degree: _Degree | None = None
    branch: _OptionalBranch = None
    start_year: int | None = None
    end_year: int | None = None
    currently_studying: bool | None = None
    grade: _OptionalGrade = None

    @field_validator("start_year")
    @classmethod
    def start_year_range(cls, v: int | None) -> int | None:
        return _validate_year_range(v)

    @field_validator("end_year")
    @classmethod
    def end_year_range(cls, v: int | None) -> int | None:
        return _validate_year_range(v)

    @model_validator(mode="after")
    def cross_field_rules_when_both_present(self) -> "EducationUpdateRequest":
        """
        Stage 1 of 2 — see the class docstring for the full contract.

        Only checks the rule when BOTH start_year and end_year are present
        in model_fields_set, i.e. both were explicitly sent in this
        request. If only one side was sent, this stage intentionally
        allows the request through — Stage 2, in the service layer, is
        responsible for validating it against the entity's persisted
        state.
        """
        fields_set = self.model_fields_set
        if (
            "start_year" in fields_set
            and "end_year" in fields_set
            and self.end_year is not None
            and self.start_year is not None
            and self.end_year < self.start_year
        ):
            raise ValueError("end_year cannot be earlier than start_year")
        return self


# ── Response schema ───────────────────────────────────────────────────────────

class EducationResponse(BaseModel):
    """Full education entry as returned to the client — owner and public
    views are identical for this module; there is no per-entry visibility
    concept (entries inherit the parent profile's visibility, enforced by
    the service layer before this schema is ever constructed)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    institution_name: str
    degree: str
    branch: str | None
    start_year: int
    end_year: int | None
    currently_studying: bool
    grade: str | None
    created_at: datetime
    updated_at: datetime