"""
app/schemas/influencer.py
──────────────────────────
Pydantic schemas for InfluencerProfile CRUD + dashboard response.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.influencer import Niche, PaymentMethod


class InfluencerProfileCreate(BaseModel):
    """
    Sent by a User with role=influencer after signup to create their profile.
    """
    bio: Optional[str]                = Field(None, max_length=1000)
    niche: Niche                      = Field(default=Niche.OTHER)
    instagram_handle: Optional[str]   = Field(None, max_length=100)
    youtube_channel:  Optional[str]   = Field(None, max_length=255)
    twitter_handle:   Optional[str]   = Field(None, max_length=100)
    follower_count:   int             = Field(default=0, ge=0)
    avg_engagement_rate: Decimal      = Field(default=Decimal("0.00"), ge=0, le=100)
    payment_method: Optional[PaymentMethod] = None
    upi_id:          Optional[str]    = Field(None, max_length=100)
    bank_account_no: Optional[str]    = Field(None, max_length=50)
    bank_ifsc:       Optional[str]    = Field(None, max_length=20)
    bank_name:       Optional[str]    = Field(None, max_length=100)

    @field_validator("upi_id")
    @classmethod
    def validate_upi(cls, v: Optional[str]) -> Optional[str]:
        if v and "@" not in v:
            raise ValueError("UPI ID must contain '@' (e.g. name@upi)")
        return v


class InfluencerProfileUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    bio: Optional[str]              = Field(None, max_length=1000)
    niche: Optional[Niche]          = None
    instagram_handle: Optional[str] = Field(None, max_length=100)
    youtube_channel:  Optional[str] = Field(None, max_length=255)
    twitter_handle:   Optional[str] = Field(None, max_length=100)
    follower_count:   Optional[int] = Field(None, ge=0)
    avg_engagement_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    payment_method: Optional[PaymentMethod] = None
    upi_id:          Optional[str]  = Field(None, max_length=100)
    bank_account_no: Optional[str]  = Field(None, max_length=50)
    bank_ifsc:       Optional[str]  = Field(None, max_length=20)
    bank_name:       Optional[str]  = Field(None, max_length=100)


class InfluencerProfileResponse(BaseModel):
    """Public profile — payment details redacted."""
    id: uuid.UUID
    user_id: uuid.UUID
    bio: Optional[str]
    niche: Niche
    instagram_handle: Optional[str]
    youtube_channel:  Optional[str]
    twitter_handle:   Optional[str]
    follower_count:   int
    avg_engagement_rate: Decimal
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InfluencerDashboardResponse(InfluencerProfileResponse):
    """
    Extended response for the influencer's own dashboard.
    Adds earnings + analytics + redacted payment method type.
    """
    total_earnings:    Decimal
    total_clicks:      int
    total_conversions: int
    payment_method: Optional[PaymentMethod]    # type only — never expose account numbers
