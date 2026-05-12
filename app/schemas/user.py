"""
app/schemas/user.py
────────────────────
Pydantic schemas for User — request bodies, response shapes, and token payloads.

Separation of concerns:
    UserCreate      ← what the client sends on signup
    UserLogin       ← what the client sends on login
    UserResponse    ← what we return (never exposes hashed_password)
    TokenResponse   ← JWT login response
    TokenPayload    ← decoded JWT contents
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


# ── Request schemas ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Signup request body."""
    full_name: str = Field(..., min_length=2, max_length=255, examples=["Riya Sharma"])
    email: EmailStr = Field(..., examples=["riya@example.com"])
    password: str  = Field(..., min_length=8, max_length=128, examples=["Str0ngPass!"])
    role: UserRole = Field(default=UserRole.USER, examples=["influencer"])

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce at least one digit and one letter."""
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class UserLogin(BaseModel):
    """Login request body."""
    email: EmailStr = Field(..., examples=["riya@example.com"])
    password: str   = Field(..., examples=["Str0ngPass!"])


class UserUpdate(BaseModel):
    """Optional partial update of profile fields."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)


# ── Response schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Safe public representation of a user — no sensitive fields."""
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}   # allows orm_mode-style construction


class TokenResponse(BaseModel):
    """Returned on successful login."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int              # seconds until expiry
    user: UserResponse


class TokenPayload(BaseModel):
    """Decoded JWT payload structure."""
    sub: str                     # user UUID as string
    role: UserRole
