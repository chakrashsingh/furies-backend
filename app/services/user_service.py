"""
app/services/user_service.py
─────────────────────────────
Business logic layer for user operations.

Routers stay thin — they delegate all DB work here.
This makes logic reusable and unit-testable without HTTP overhead.
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


# ── Read helpers ──────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Return a User by email, or None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Return a User by UUID, or None if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ── Write helpers ─────────────────────────────────────────────────────────────

async def create_user(db: AsyncSession, payload: UserCreate) -> User:
    """
    Hash the password and persist a new User row.
    Raises ValueError if email is already registered.
    """
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise ValueError("A user with this email already exists.")

    user = User(
        full_name=payload.full_name,
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()    # write to DB within transaction, get generated id
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Return the User if credentials are valid and account is active.
    Returns None on any mismatch (intentionally vague for security).
    """
    user = await get_user_by_email(db, email.lower().strip())
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
