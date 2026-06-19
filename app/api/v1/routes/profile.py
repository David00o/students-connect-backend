from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import (
    ProfileCreateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    PublicProfileResponse,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profile"])


# ── Route-level response envelope ────────────────────────────────────────────
# Only used by POST /profile, which returns success + message + profile data.
# Defined here rather than in schemas/profile.py to keep the schema file
# focused on reusable types; this envelope is only needed by this one route.

class ProfileCreateResponse(BaseModel):
    success: bool = True
    message: str
    profile: ProfileResponse


# ── Dependency ────────────────────────────────────────────────────────────────

def _get_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(ProfileRepository(db))


# ── 1. Create profile ─────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ProfileCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the authenticated user's profile",
)
async def create_profile(
    payload: ProfileCreateRequest,
    service: ProfileService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> ProfileCreateResponse:
    profile = await service.create_profile(user=current_user, payload=payload)
    return ProfileCreateResponse(
        message="Profile created successfully.",
        profile=ProfileResponse.model_validate(profile),
    )


# ── 2. Get own profile ────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user's profile",
)
async def get_my_profile(
    service: ProfileService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    profile = await service.get_my_profile(user=current_user)
    return ProfileResponse.model_validate(profile)


# ── 3. Update own profile ─────────────────────────────────────────────────────

@router.put(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update the authenticated user's profile (partial update supported)",
)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    service: ProfileService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    profile = await service.update_my_profile(user=current_user, payload=payload)
    return ProfileResponse.model_validate(profile)


# ── 4. Get public profile ─────────────────────────────────────────────────────

@router.get(
    "/{username}",
    response_model=PublicProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Return a public profile by username",
)
async def get_public_profile(
    username: str,
    service: ProfileService = Depends(_get_service),
) -> PublicProfileResponse:
    profile = await service.get_public_profile(username=username)
    return PublicProfileResponse.model_validate(profile)