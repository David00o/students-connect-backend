import logging
import uuid

from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.models.education import Education
from app.models.user import User
from app.repositories.education_repository import EducationRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.education import EducationCreateRequest, EducationUpdateRequest

logger = logging.getLogger(__name__)


class EducationService:
    def __init__(
        self,
        education_repository: EducationRepository,
        profile_repository: ProfileRepository,
    ) -> None:
        self._repo = education_repository
        self._profile_repo = profile_repository

    # ── 1. Create education entry ─────────────────────────────────────────────

    async def create_education(
        self,
        *,
        user: User,
        payload: EducationCreateRequest,
    ) -> Education:
        # A profile is a prerequisite for adding education — a user cannot
        # attach an education entry before completing profile creation.
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundException("Profile not found.")

        education = Education(
            profile_id=profile.id,
            institution_name=payload.institution_name,
            degree=payload.degree,
            branch=payload.branch,
            start_year=payload.start_year,
            end_year=payload.end_year,
            currently_studying=payload.currently_studying,
            grade=payload.grade,
        )

        await self._repo.create(education)
        logger.info(
            "Education entry created for user %s (@%s) — %s, %s",
            user.id,
            profile.username,
            education.institution_name,
            education.degree,
        )
        return education

    # ── 2. Get own education entries ──────────────────────────────────────────

    async def get_my_educations(
        self,
        *,
        user: User,
    ) -> list[Education]:
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundException("Profile not found.")

        return await self._repo.get_by_profile_id(profile.id)

    # ── 3. Update an education entry ──────────────────────────────────────────

    async def update_education(
        self,
        *,
        user: User,
        education_id: uuid.UUID,
        payload: EducationUpdateRequest,
    ) -> Education:
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundException("Profile not found.")

        education = await self._repo.get_by_id(education_id)
        if education is None:
            raise NotFoundException("Education entry not found.")

        # Ownership check — a user may only modify education entries
        # attached to their own profile.
        if education.profile_id != profile.id:
            logger.warning(
                "User %s attempted to update education entry %s owned by a different profile",
                user.id,
                education_id,
            )
            raise ForbiddenException(
                "You do not have permission to modify this education entry."
            )

        # ── Compute the final merged state WITHOUT mutating the ORM object yet ──
        # We must validate the FINAL state (persisted values merged with the
        # PATCH payload) before calling setattr() on the live `education`
        # object. Validating after mutation would leave a dirty, invalid
        # ORM instance sitting in the session's identity map at the moment
        # the exception is raised. Although this project's session is
        # configured with autoflush=False (see app/db/session.py), so an
        # unrelated query within the same request would not flush it
        # prematurely, relying on that as the only safeguard is fragile —
        # any future code path that calls flush()/commit() on this same
        # session for an unrelated reason would hit the database's CHECK
        # constraint and surface a confusing IntegrityError instead of the
        # clean BadRequestException we intend here. Validating BEFORE
        # mutation means setattr() is only ever called once we already know
        # the result is valid — the ORM object is never observably invalid,
        # even momentarily.
        fields_set = payload.model_fields_set
        final_start_year = (
            payload.start_year if "start_year" in fields_set else education.start_year
        )
        final_end_year = (
            payload.end_year if "end_year" in fields_set else education.end_year
        )

        # ── Stage 2 cross-field validation ──────────────────────────────────
        # The schema (EducationUpdateRequest) only validates this rule
        # when BOTH start_year and end_year are present in the SAME
        # request — see the schema's docstring for the full two-stage
        # contract. Here, after merging the PATCH payload with the
        # persisted entity's current values, we validate the same rule
        # against the entity's FINAL state — which may combine a field
        # just sent in this request with a field that was already
        # persisted from a previous request. This is the only way to
        # catch a sequence of individually-valid PATCH requests that
        # together would leave the row in a contradictory state (e.g. a
        # prior request set start_year=2024, and this request sends only
        # {"end_year": 2020} — the schema alone cannot see the conflict
        # because start_year never appears in this request).
        #
        # This intentionally re-implements the SAME rule as the schema's
        # Stage 1 validator (ck_educations_end_after_start) — not a new
        # business rule — applied to the merged state rather than the raw
        # payload.
        #
        # Note: the previous mutual-exclusivity rule between
        # currently_studying and end_year has been removed (see
        # alembic/versions/004_education_end_year_rule.py). end_year now
        # represents the expected graduation year (when
        # currently_studying is true) or the actual graduation year (when
        # false), and is valid in either case — there is nothing to
        # validate between these two fields anymore.
        if final_end_year is not None and final_end_year < final_start_year:
            raise BadRequestException(
                "end_year cannot be earlier than start_year"
            )

        # Only now, after validation has passed, apply the PATCH payload to
        # the live ORM object. model_fields_set contains only keys present
        # in the parsed payload, so omitted fields are never overwritten —
        # identical pattern to ProfileService.update_my_profile.
        for field in fields_set:
            if not hasattr(education, field):
                logger.warning(
                    "EducationUpdateRequest field '%s' has no counterpart on Education — skipped",
                    field,
                )
                continue
            setattr(education, field, getattr(payload, field))

        await self._repo.update(education)
        logger.info(
            "Education entry %s updated for user %s", education_id, user.id
        )
        return education

    # ── 4. Delete an education entry ──────────────────────────────────────────

    async def delete_education(
        self,
        *,
        user: User,
        education_id: uuid.UUID,
    ) -> None:
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundException("Profile not found.")

        education = await self._repo.get_by_id(education_id)
        if education is None:
            raise NotFoundException("Education entry not found.")

        if education.profile_id != profile.id:
            logger.warning(
                "User %s attempted to delete education entry %s owned by a different profile",
                user.id,
                education_id,
            )
            raise ForbiddenException(
                "You do not have permission to delete this education entry."
            )

        await self._repo.delete(education)
        logger.info(
            "Education entry %s deleted for user %s", education_id, user.id
        )