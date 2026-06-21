import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.education import Education


class EducationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, education: Education) -> Education:
        self._db.add(education)
        await self._db.flush()  # populate id/created_at without committing
        return education

    async def get_by_id(self, education_id: uuid.UUID) -> Education | None:
        result = await self._db.execute(
            select(Education).where(Education.id == education_id)
        )
        return result.scalar_one_or_none()

    async def get_by_profile_id(self, profile_id: uuid.UUID) -> list[Education]:
        """
        All education entries for a profile, ordered:
          1. currently_studying DESC — active/in-progress entries surface
             first, since they are the most relevant fact about a user's
             current academic status (mirrors the product reasoning behind
             the partial index ix_educations_profile_id_currently_studying
             in the migration: this is the single most common "what is
             this person doing right now" lookup).
          2. start_year DESC — among entries of equal currently_studying
             status, the most recently started program is shown first,
             giving a natural reverse-chronological timeline (most recent
             degree first, oldest schooling last).
          3. created_at DESC — final tiebreaker for entries that share
             both currently_studying and start_year (e.g. two concurrent
             programs started the same year); the most recently added
             record is shown first as a stable, deterministic tiebreaker.
        """
        result = await self._db.execute(
            select(Education)
            .where(Education.profile_id == profile_id)
            .order_by(
                Education.currently_studying.desc(),
                Education.start_year.desc(),
                Education.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def update(self, education: Education) -> Education:
        """
        Flush dirty ORM state to the DB, then refresh.

        Identical reasoning to ProfileRepository.update(): an UPDATE
        statement causes SQLAlchemy to expire any column with a server-side
        onupdate/default (here: updated_at), since it cannot know the new
        server-computed value without a re-query. If that expired attribute
        is accessed later — e.g. by Pydantic's model_validate() in the route
        layer — SQLAlchemy must perform an implicit lazy-load, which requires
        an active async/greenlet context. Outside of it, this raises
        MissingGreenlet (or DetachedInstanceError once the session has
        closed) — the exact bug already diagnosed and fixed in the Profile
        module.

        refresh() re-selects the row immediately, while still inside the
        awaited call, so every attribute (including updated_at) is fully
        loaded in memory before this method returns — no later implicit
        I/O is possible.
        """
        await self._db.flush()
        await self._db.refresh(education)
        return education

    async def delete(self, education: Education) -> None:
        await self._db.delete(education)
        await self._db.flush()