import logging

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.models.profile import Profile, ProfileVisibility
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ProfileCreateRequest, ProfileUpdateRequest

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._repo = profile_repository

    # ── 1. Create profile ─────────────────────────────────────────────────────

    async def create_profile(
        self,
        *,
        user: User,
        payload: ProfileCreateRequest,
    ) -> Profile:
        # A user can only have one profile
        existing = await self._repo.get_by_user_id(user.id)
        if existing is not None:
            logger.warning(
                "Duplicate profile creation attempt by user %s", user.id
            )
            raise ConflictException("Profile already exists for this account.")

        # Username must be globally unique (case-insensitive)
        if await self._repo.username_exists(payload.username):
            logger.warning(
                "Username conflict on profile creation: '%s' (user %s)",
                payload.username,
                user.id,
            )
            raise ConflictException("Username is already taken.")

        profile = Profile(
            user_id=user.id,
            username=payload.username,  # already lowercased by schema validator
            first_name=payload.first_name,
            last_name=payload.last_name,
            profile_photo=payload.profile_photo,
            cover_photo=payload.cover_photo,
            date_of_birth=payload.date_of_birth,
            bio=payload.bio,
            about=payload.about,
            college=payload.college,
            branch=payload.branch,
            academic_year=payload.academic_year,
            profile_visibility=payload.profile_visibility,
        )

        await self._repo.create(profile)
        logger.info("Profile created for user %s (@%s)", user.id, profile.username)
        return profile

    # ── 2. Get own profile ────────────────────────────────────────────────────

    async def get_my_profile(
        self,
        *,
        user: User,
    ) -> Profile:
        profile = await self._repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundException("Profile not found.")
        return profile

    # ── 3. Update own profile ─────────────────────────────────────────────────

    async def update_my_profile(
        self,
        *,
        user: User,
        payload: ProfileUpdateRequest,
    ) -> Profile:
        profile = await self._repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundException("Profile not found.")

        # Only touch fields the client explicitly included in the request.
        # model_fields_set contains only keys present in the parsed payload,
        # so omitted fields are never overwritten with None.
        #
        # Username is intentionally absent from ProfileUpdateRequest so it
        # cannot be changed here. If username updates are introduced in the
        # future, add a uniqueness check (username_exists) before this loop
        # — identical to the check in create_profile — and handle the case
        # where the new username belongs to the same user.
        for field in payload.model_fields_set:
            if not hasattr(profile, field):
                # Defensive guard: ProfileUpdateRequest must not expose fields
                # that do not exist on the Profile model (e.g. after a schema
                # refactor). Log and skip rather than raise, so a single bad
                # field does not abort the whole update.
                logger.warning(
                    "ProfileUpdateRequest field '%s' has no counterpart on Profile — skipped",
                    field,
                )
                continue
            setattr(profile, field, getattr(payload, field))

        await self._repo.update(profile)
        logger.info("Profile updated for user %s", user.id)
        return profile

    # ── 4. Get public profile ─────────────────────────────────────────────────

    async def get_public_profile(
        self,
        username: str,
    ) -> Profile:
        profile = await self._repo.get_by_username(username)
        if profile is None:
            raise NotFoundException("Profile not found.")

        if profile.profile_visibility == ProfileVisibility.PUBLIC:
            return profile

        if profile.profile_visibility == ProfileVisibility.PRIVATE:
            raise ForbiddenException("This profile is private.")

        if profile.profile_visibility == ProfileVisibility.CONNECTIONS:
            # TODO(connections-module): replace this placeholder with a real check.
            # When the Connections module is built:
            #   1. Accept the requesting User as a parameter (requires route change).
            #   2. Call a ConnectionRepository method such as:
            #          are_connected(user_a_id, user_b_id) -> bool
            #   3. Return the profile if connected, raise ForbiddenException if not.
            # Tracked in: connections module implementation.
            raise ForbiddenException("This profile is visible to connections only.")

        # Unreachable — all enum variants handled above.
        # Guards against future visibility values being added without updating
        # this method.
        raise ForbiddenException("Profile is not publicly accessible.")