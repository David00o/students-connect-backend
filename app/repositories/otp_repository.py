from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.otp import OTP, OTPPurpose


class OTPRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, email: str, otp_code: str, purpose: OTPPurpose) -> OTP:
        """Invalidate any previous OTPs for the same email+purpose, then create new."""
        # Mark old OTPs as used
        await self._db.execute(
            update(OTP)
            .where(OTP.email == email.lower(), OTP.purpose == purpose, OTP.is_used == False)  # noqa: E712
            .values(is_used=True)
        )

        otp = OTP(
            email=email.lower(),
            otp_code=otp_code,
            purpose=purpose,
            is_used=False,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        )
        self._db.add(otp)
        await self._db.flush()
        return otp

    async def get_valid(
        self, email: str, otp_code: str, purpose: OTPPurpose
    ) -> OTP | None:
        """Return a matching, unused, non-expired OTP or None."""
        result = await self._db.execute(
            select(OTP).where(
                OTP.email == email.lower(),
                OTP.otp_code == otp_code,
                OTP.purpose == purpose,
                OTP.is_used == False,  # noqa: E712
                OTP.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, otp: OTP) -> None:
        otp.is_used = True
        await self._db.flush()
