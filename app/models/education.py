import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Education(Base):
    __tablename__ = "educations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Institution & program ────────────────────────────────────────────────
    institution_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    degree: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    branch: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ── Duration ──────────────────────────────────────────────────────────────
    # end_year represents the expected graduation year when
    # currently_studying is true, or the actual graduation year when
    # currently_studying is false. end_year is independently optional in
    # both cases — there is no mutual-exclusivity rule between the two
    # fields (this was previously enforced and has since been removed;
    # see alembic/versions/004_education_end_year_rule.py).
    start_year: Mapped[int] = mapped_column(
        SmallInteger(),
        nullable=False,
    )
    end_year: Mapped[int | None] = mapped_column(
        SmallInteger(),
        nullable=True,
    )
    currently_studying: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default="false",
    )

    # ── Performance ───────────────────────────────────────────────────────────
    # Generic free-text grade — supports CGPA, percentage, letter grades,
    # or qualitative outcomes (e.g. "Distinction", "Pass"), since grading
    # systems vary widely across countries and institutions. No enum and
    # no numeric type — kept as plain String to match the migration exactly.
    grade: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    profile: Mapped["Profile"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Profile",
        back_populates="educations",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Education id={self.id} institution_name={self.institution_name}>"