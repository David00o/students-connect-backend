import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.education_repository import EducationRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.education import (
    EducationCreateRequest,
    EducationResponse,
    EducationUpdateRequest,
)
from app.services.education_service import EducationService

router = APIRouter(prefix="/education", tags=["Education"])


# ── Route-level response envelope ────────────────────────────────────────────
# Only used by POST /education, which returns success + message + entry data.
# Defined here rather than in schemas/education.py to keep the schema file
# focused on reusable types — same pattern as ProfileCreateResponse in
# routes/profile.py.

class EducationCreateResponse(BaseModel):
    success: bool = True
    message: str
    education: EducationResponse


# ── Dependency ────────────────────────────────────────────────────────────────

def _get_service(db: AsyncSession = Depends(get_db)) -> EducationService:
    return EducationService(EducationRepository(db), ProfileRepository(db))


# ── 1. Create education entry ─────────────────────────────────────────────────

@router.post(
    "",
    response_model=EducationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new education entry for the authenticated user's profile",
)
async def create_education(
    payload: EducationCreateRequest,
    service: EducationService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> EducationCreateResponse:
    education = await service.create_education(user=current_user, payload=payload)
    return EducationCreateResponse(
        message="Education entry created successfully.",
        education=EducationResponse.model_validate(education),
    )


# ── 2. List own education entries ─────────────────────────────────────────────

@router.get(
    "/me",
    response_model=list[EducationResponse],
    status_code=status.HTTP_200_OK,
    summary="List the authenticated user's education entries",
)
async def get_my_educations(
    service: EducationService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> list[EducationResponse]:
    educations = await service.get_my_educations(user=current_user)
    return [EducationResponse.model_validate(entry) for entry in educations]


# ── 3. Update an education entry ──────────────────────────────────────────────

@router.put(
    "/{education_id}",
    response_model=EducationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an education entry (partial update supported)",
)
async def update_education(
    education_id: uuid.UUID,
    payload: EducationUpdateRequest,
    service: EducationService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> EducationResponse:
    education = await service.update_education(
        user=current_user,
        education_id=education_id,
        payload=payload,
    )
    return EducationResponse.model_validate(education)


# ── 4. Delete an education entry ──────────────────────────────────────────────

@router.delete(
    "/{education_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an education entry",
)
async def delete_education(
    education_id: uuid.UUID,
    service: EducationService = Depends(_get_service),
    current_user: User = Depends(get_current_user),
) -> None:
    await service.delete_education(user=current_user, education_id=education_id)