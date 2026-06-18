import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AccountStatus, User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: str | uuid.UUID) -> User | None:
        result = await self._db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_email_or_phone(self, email_or_phone: str) -> User | None:
        result = await self._db.execute(
            select(User).where(
                (User.email == email_or_phone.lower())
                | (User.phone_number == email_or_phone)
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        first_name: str,  # stored on Profile; kept here for clarity
        last_name: str,
        date_of_birth: object,
    ) -> User:
        """Create a user record (no password yet — set after OTP verification)."""
        user = User(
            email=email.lower(),
            account_status=AccountStatus.ACTIVE,
        )
        self._db.add(user)
        await self._db.flush()  # get the generated id without committing
        return user

    async def set_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        user.email_verified = True
        await self._db.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def update_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self._db.flush()

    async def soft_delete(self, user: User) -> None:
        user.account_status = AccountStatus.DELETED
        await self._db.flush()
