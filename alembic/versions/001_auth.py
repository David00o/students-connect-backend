"""create users and otps tables

Revision ID: 001_auth
Revises:
Create Date: 2026-06-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_auth"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Declare enums once here so the same object is reused in both
# create() and create_table(). Passing create_type=False on the
# column-level Enum tells SQLAlchemy not to emit a second CREATE TYPE
# inside create_table — the type is already created by .create() above.
account_status_enum = postgresql.ENUM(
    "active", "suspended", "banned", "deleted",
    name="account_status_enum",
    create_type=False,  # we call .create() explicitly below
)

otp_purpose_enum = postgresql.ENUM(
    "email_verification", "password_reset",
    name="otp_purpose_enum",
    create_type=False,  # we call .create() explicitly below
)


def upgrade() -> None:
    # ── Create enum types first, exactly once each ─────────────────────────
    account_status_enum.create(op.get_bind(), checkfirst=True)
    otp_purpose_enum.create(op.get_bind(), checkfirst=True)

    # ── Users table ────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "account_status",
            account_status_enum,  # reuse the same object — no second CREATE TYPE
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)

    # ── OTPs table ─────────────────────────────────────────────────────────
    op.create_table(
        "otps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("otp_code", sa.String(6), nullable=False),
        sa.Column(
            "purpose",
            otp_purpose_enum,  # reuse the same object — no second CREATE TYPE
            nullable=False,
        ),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_otps_email", "otps", ["email"])


def downgrade() -> None:
    op.drop_table("otps")
    op.drop_table("users")

    # Drop enum types after tables are gone
    otp_purpose_enum.drop(op.get_bind(), checkfirst=True)
    account_status_enum.drop(op.get_bind(), checkfirst=True)