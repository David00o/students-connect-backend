import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OTPPurpose(enum.StrEnum):
    """
    Use enum.StrEnum (Python 3.11+) so that str(member) == member.value.
    This is required for asyncpg, which encodes PostgreSQL enum values by
    calling str() on the Python object — bypassing SQLAlchemy's bind processor.
    With (str, enum.Enum) on Python 3.12, str() returns the qualified name
    'OTPPurpose.EMAIL_VERIFICATION' instead of the value 'email_verification',
    causing a DuplicateObjectError / invalid input value for enum.
    """
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class OTP(Base):
    __tablename__ = "otps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    otp_code: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
    )
    purpose: Mapped[OTPPurpose] = mapped_column(
        Enum(
            OTPPurpose,
            name="otp_purpose_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OTP email={self.email} purpose={self.purpose}>"