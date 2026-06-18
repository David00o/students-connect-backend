from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import AccountStatus, User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve Bearer token → User. Raises 401/403 on failure."""
    user_id = decode_access_token(credentials.credentials)

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException("User not found")

    if user.account_status == AccountStatus.BANNED:
        raise ForbiddenException("Account is banned")

    if user.account_status == AccountStatus.SUSPENDED:
        raise ForbiddenException("Account is suspended")

    if user.account_status == AccountStatus.DELETED:
        raise ForbiddenException("Account has been deleted")

    return user


async def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require email-verified account."""
    if not current_user.email_verified:
        raise ForbiddenException("Email not verified")
    return current_user
