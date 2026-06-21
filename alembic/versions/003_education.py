"""create educations table

Revision ID: 003_education
Revises: 002_profile
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_education"
down_revision: Union[str, None] = "002_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "educations",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),

        # Foreign key — named explicitly so dropping/inspecting the
        # constraint in production is unambiguous.
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_educations_profile_id",
            ondelete="CASCADE",
        ),

        # ── Institution & program ────────────────────────────────────────
        sa.Column("institution_name", sa.String(255), nullable=False),
        sa.Column("degree", sa.String(100), nullable=False),
        sa.Column("branch", sa.String(100), nullable=True),

        # ── Duration ──────────────────────────────────────────────────────
        sa.Column("start_year", sa.SmallInteger(), nullable=False),
        sa.Column("end_year", sa.SmallInteger(), nullable=True),
        sa.Column(
            "currently_studying",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),

        # ── Performance ───────────────────────────────────────────────────
        # Generic free-text grade — supports CGPA ("9.87"), percentage
        # ("85%"), letter grades ("A+"), or qualitative outcomes
        # ("Distinction", "Pass"), since grading systems vary widely
        # across countries and institutions. No numeric range constraint
        # is possible or appropriate on a free-text field; only a
        # blank-string guard applies, consistent with institution_name
        # and degree below.
        sa.Column("grade", sa.String(50), nullable=True),

        # ── Timestamps ────────────────────────────────────────────────────
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
        # Institution and degree must be non-empty strings (guards against
        # blank updates bypassing application validation).
        sa.CheckConstraint(
            "length(trim(institution_name)) > 0",
            name="ck_educations_institution_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(degree)) > 0",
            name="ck_educations_degree_not_blank",
        ),

        # Grade, if provided, must not be an empty or whitespace-only
        # string. No numeric range applies — grade is free text by design.
        sa.CheckConstraint(
            "grade IS NULL OR length(trim(grade)) > 0",
            name="ck_educations_grade_not_blank",
        ),

        # Year sanity bounds — no living user started school before 1950;
        # 2100 gives ~74 years of headroom without a moving upper bound.
        sa.CheckConstraint(
            "start_year >= 1950 AND start_year <= 2100",
            name="ck_educations_start_year_range",
        ),
        sa.CheckConstraint(
            "end_year IS NULL OR (end_year >= 1950 AND end_year <= 2100)",
            name="ck_educations_end_year_range",
        ),

        # An entry cannot end before it starts. Equal years are allowed
        # (e.g. a one-year diploma).
        sa.CheckConstraint(
            "end_year IS NULL OR end_year >= start_year",
            name="ck_educations_end_after_start",
        ),

        # An in-progress entry cannot simultaneously carry a fixed end
        # year — that would be a contradictory state.
        sa.CheckConstraint(
            "(currently_studying = false) OR (end_year IS NULL)",
            name="ck_educations_currently_studying_no_end_year",
        ),
    )

    # ── Indexes ────────────────────────────────────────────────────────────

    # profile_id: primary access pattern — "get all education entries
    # for this profile." Non-unique; a profile has many entries.
    op.create_index(
        "ix_educations_profile_id",
        "educations",
        ["profile_id"],
    )

    # Partial index on (profile_id, currently_studying) where true —
    # supports "what is this user currently studying" lookups used when
    # rendering a compact profile card. Partial because currently_studying
    # = true is a small minority of rows at any time.
    op.create_index(
        "ix_educations_profile_id_currently_studying",
        "educations",
        ["profile_id", "currently_studying"],
        postgresql_where=sa.text("currently_studying = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_educations_profile_id_currently_studying", table_name="educations")
    op.drop_index("ix_educations_profile_id", table_name="educations")
    op.drop_table("educations")