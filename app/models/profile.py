import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProfileVisibility(enum.StrEnum):
    """
    Use enum.StrEnum so that str(member) == member.value.
    asyncpg encodes PostgreSQL enum values via str() — bypassing SQLAlchemy's
    bind processor — so this is required for correct wire encoding.
    """
    PUBLIC = "public"
    CONNECTIONS = "connections"
    PRIVATE = "private"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # ── Media ─────────────────────────────────────────────────────────────────
    profile_photo: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    cover_photo: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # ── Personal details ──────────────────────────────────────────────────────
    date_of_birth: Mapped[date | None] = mapped_column(
        Date(),
        nullable=True,
    )
    bio: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    about: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )

    # ── Academic details ──────────────────────────────────────────────────────
    college: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    branch: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    academic_year: Mapped[int | None] = mapped_column(
        SmallInteger(),
        nullable=True,
    )

    # ── Gamification ──────────────────────────────────────────────────────────
    profile_score: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=0,
        server_default="0",
    )

    # ── Privacy ───────────────────────────────────────────────────────────────
    profile_visibility: Mapped[ProfileVisibility] = mapped_column(
        Enum(
            ProfileVisibility,
            name="profile_visibility_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ProfileVisibility.PUBLIC,
        server_default="public",
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
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="profile",
        lazy="raise",
    )
    educations: Mapped[list["Education"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Education",
        back_populates="profile",
        lazy="raise",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Profile id={self.id} username={self.username}>"