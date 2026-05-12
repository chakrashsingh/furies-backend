"""
app/core/dependencies.py
─────────────────────────
Reusable FastAPI Depends() guards for authentication and role enforcement.

Usage in any router:
    # Any authenticated user
    @router.get("/me")
    async def me(current_user: User = Depends(get_current_user)):
        ...

    # Influencer only
    @router.get("/dashboard")
    async def dashboard(user: User = Depends(require_role(UserRole.INFLUENCER))):
        ...
"""

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_id

import uuid

# Bearer token extractor — reads `Authorization: Bearer <token>` header
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Core auth dependency.
    1. Extracts Bearer token from Authorization header
    2. Decodes + validates JWT signature and expiry
    3. Loads the user from DB to ensure they still exist and are active
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: UserRole) -> Callable:
    """
    Factory that returns a dependency enforcing one of the given roles.

    Example:
        Depends(require_role(UserRole.BRAND, UserRole.INFLUENCER))
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted. Required role(s): {[r.value for r in roles]}",
            )
        return current_user
    return role_checker


# ── Convenience shortcuts ─────────────────────────────────────────────────────
require_influencer = require_role(UserRole.INFLUENCER)
require_brand       = require_role(UserRole.BRAND)
require_normal_user = require_role(UserRole.USER)
# Admins in the future: require_admin = require_role(UserRole.ADMIN)
