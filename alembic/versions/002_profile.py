"""create profiles table

Revision ID: 002_profile
Revises: 001_auth
Create Date: 2026-06-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_profile"
down_revision: Union[str, None] = "001_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Declared with create_type=False — .create() is called explicitly below
# so PostgreSQL never sees a duplicate CREATE TYPE.
profile_visibility_enum = postgresql.ENUM(
    "public", "connections", "private",
    name="profile_visibility_enum",
    create_type=False,
)


def upgrade() -> None:
    # ── Create enum type first, exactly once ───────────────────────────────
    profile_visibility_enum.create(op.get_bind(), checkfirst=True)

    # ── Profiles table ─────────────────────────────────────────────────────
    op.create_table(
        "profiles",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),

        # Foreign key — named explicitly so dropping/inspecting the
        # constraint in production is unambiguous.
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_profiles_user_id",
            ondelete="CASCADE",
        ),

        # ── Identity ────────────────────────────────────────────────────
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(50), nullable=False),
        sa.Column("last_name", sa.String(50), nullable=False),

        # ── Media (cloud storage URLs) ───────────────────────────────────
        sa.Column("profile_photo", sa.String(500), nullable=True),
        sa.Column("cover_photo", sa.String(500), nullable=True),

        # ── Personal details ─────────────────────────────────────────────
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),

        # ── Academic details ─────────────────────────────────────────────
        sa.Column("college", sa.String(255), nullable=True),
        sa.Column("branch", sa.String(100), nullable=True),
        sa.Column("academic_year", sa.SmallInteger(), nullable=True),

        # ── Gamification ─────────────────────────────────────────────────
        sa.Column(
            "profile_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        # ── Privacy ──────────────────────────────────────────────────────
        sa.Column(
            "profile_visibility",
            profile_visibility_enum,
            nullable=False,
            server_default="public",
        ),

        # ── Timestamps ───────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),

        # ── CHECK constraints ─────────────────────────────────────────────
        # Username: 3-50 chars, alphanumeric + underscore + dot only.
        # Enforced at DB level independent of application validation.
        sa.CheckConstraint(
            r"username ~ '^[a-zA-Z0-9_.]{3,50}$'",
            name="ck_profiles_username_format",
        ),

        # Names must be non-empty strings (guards against blank updates).
        sa.CheckConstraint(
            "length(trim(first_name)) > 0",
            name="ck_profiles_first_name_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(last_name)) > 0",
            name="ck_profiles_last_name_not_blank",
        ),

        # Academic year must be 1–8, covering undergraduate through
        # extended/postgraduate programs including dual degrees and PhDs.
        sa.CheckConstraint(
            "academic_year IS NULL OR (academic_year >= 1 AND academic_year <= 8)",
            name="ck_profiles_academic_year_range",
        ),

        # Profile score is additive and must never go negative.
        sa.CheckConstraint(
            "profile_score >= 0",
            name="ck_profiles_score_non_negative",
        ),

        # Date of birth must be in the past.
        sa.CheckConstraint(
            "date_of_birth IS NULL OR date_of_birth < CURRENT_DATE",
            name="ck_profiles_dob_in_past",
        ),
    )

    # ── Indexes ────────────────────────────────────────────────────────────

    # user_id: unique enforces the 1-to-1 relationship at the DB level.
    op.create_index(
        "ix_profiles_user_id",
        "profiles",
        ["user_id"],
        unique=True,
    )

    # username: functional lower() index makes username lookup and the
    # unique constraint case-insensitive. 'Alice' and 'alice' are the same
    # username on a social network. The index expression must match the
    # query expression — the service layer must always query lower(username).
    op.create_index(
        "ix_profiles_username_lower",
        "profiles",
        [sa.text("lower(username)")],
        unique=True,
    )

    # college: used heavily for "find students at my college" queries.
    # A plain B-tree is sufficient; GIN/trigram can be added later if
    # full-text search is introduced.
    op.create_index(
        "ix_profiles_college",
        "profiles",
        ["college"],
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_college", table_name="profiles")
    op.drop_index("ix_profiles_username_lower", table_name="profiles")
    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_table("profiles")

    profile_visibility_enum.drop(op.get_bind(), checkfirst=True)