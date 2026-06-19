import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile


class ProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, profile: Profile) -> Profile:
        self._db.add(profile)
        await self._db.flush()  # populate id without committing
        return profile

    async def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        result = await self._db.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Profile | None:
        """Case-insensitive lookup — uses the lower(username) functional index."""
        result = await self._db.execute(
            select(Profile).where(func.lower(Profile.username) == username.lower())
        )
        return result.scalar_one_or_none()

    async def username_exists(self, username: str) -> bool:
        """Case-insensitive existence check — uses the lower(username) functional index."""
        result = await self._db.execute(
            select(Profile.id).where(func.lower(Profile.username) == username.lower())
        )
        return result.scalar_one_or_none() is not None

    async def update(self, profile: Profile) -> Profile:
        """
        Flush dirty ORM state to the DB, then refresh.

        An UPDATE statement causes SQLAlchemy to expire any column with a
        server-side onupdate/default (here: updated_at), since it cannot
        know the new server-computed value without a re-query. If that
        expired attribute is accessed later — e.g. by Pydantic's
        model_validate() in the route layer — SQLAlchemy must perform an
        implicit lazy-load. That lazy-load requires an active async/greenlet
        context; outside of it, it raises MissingGreenlet (or
        DetachedInstanceError once the session has closed).

        refresh() re-selects the row immediately, while we are still
        inside the awaited async call, so every attribute (including
        updated_at) is fully loaded in memory before this method returns.
        This mirrors what create() gets "for free": after an INSERT,
        SQLAlchemy populates server-default columns synchronously as part
        of the same flush — no separate refresh is needed there.
        """
        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def delete(self, profile: Profile) -> None:
        await self._db.delete(profile)
        await self._db.flush()