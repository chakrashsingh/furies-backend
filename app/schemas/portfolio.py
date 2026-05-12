"""
app/schemas/portfolio.py
─────────────────────────
Pydantic schemas for Portfolio, PortfolioItem, PhysicalStats,
CreatorStats, and CustomField.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

from app.models.portfolio import (
    EyeColor, HairColor, IndustryType,
    PortfolioItemType, SkinTone,
)


# ── Portfolio Items ───────────────────────────────────────────────────────────

class PortfolioItemCreate(BaseModel):
    item_type:     PortfolioItemType
    title:         Optional[str]  = Field(None, max_length=255)
    description:   Optional[str]  = Field(None, max_length=2000)
    media_url:     Optional[str]  = Field(None, max_length=500,
        description="Direct image URL or YouTube/Reels link")
    thumbnail_url: Optional[str]  = Field(None, max_length=500)
    brand_name:    Optional[str]  = Field(None, max_length=255)
    results:       Optional[str]  = Field(None, max_length=1000,
        description="e.g. '2.3M views, 15% engagement rate'")
    display_order: int            = Field(default=0, ge=0)
    collab_date:   Optional[datetime] = None


class PortfolioItemResponse(BaseModel):
    id:            uuid.UUID
    portfolio_id:  uuid.UUID
    item_type:     PortfolioItemType
    title:         Optional[str]
    description:   Optional[str]
    media_url:     Optional[str]
    thumbnail_url: Optional[str]
    brand_name:    Optional[str]
    results:       Optional[str]
    display_order: int
    collab_date:   Optional[datetime]
    created_at:    datetime
    model_config = {"from_attributes": True}


# ── Physical Stats ────────────────────────────────────────────────────────────

class PhysicalStatsCreate(BaseModel):
    height_cm:         Optional[int]     = Field(None, ge=100, le=250,
        description="Height in centimetres e.g. 175")
    weight_kg:         Optional[Decimal] = Field(None, ge=30,  le=200,
        description="Weight in kilograms e.g. 62.5")
    bust_cm:           Optional[int]     = Field(None, ge=50,  le=150)
    waist_cm:          Optional[int]     = Field(None, ge=40,  le=150)
    hips_cm:           Optional[int]     = Field(None, ge=50,  le=160)
    shoe_size_eu:      Optional[int]     = Field(None, ge=30,  le=50)
    dress_size:        Optional[str]     = Field(None, max_length=10,
        description="XS / S / M / L / XL / XXL or numeric e.g. 32")
    skin_tone:         Optional[SkinTone]  = None
    hair_color:        Optional[HairColor] = None
    eye_color:         Optional[EyeColor]  = None
    years_experience:  Optional[int]     = Field(None, ge=0, le=50)
    languages:         Optional[str]     = Field(None, max_length=255,
        description="Comma-separated e.g. 'Hindi,English,Punjabi'")
    willing_to_travel: bool              = True


class PhysicalStatsResponse(PhysicalStatsCreate):
    id:           uuid.UUID
    portfolio_id: uuid.UUID
    model_config = {"from_attributes": True}


# ── Creator Stats ─────────────────────────────────────────────────────────────

class CreatorStatsCreate(BaseModel):
    primary_platform:      Optional[str] = Field(None, max_length=50,
        description="YouTube / Instagram / TikTok / Podcast / Twitch")
    subscriber_count:      Optional[int] = Field(None, ge=0)
    avg_views_per_video:   Optional[int] = Field(None, ge=0)
    avg_likes_per_post:    Optional[int] = Field(None, ge=0)
    avg_comments:          Optional[int] = Field(None, ge=0)
    posting_frequency:     Optional[str] = Field(None, max_length=100,
        description="e.g. '3 videos/week'")
    audience_age_range:    Optional[str] = Field(None, max_length=50,
        description="e.g. '18-24'")
    audience_gender_split: Optional[str] = Field(None, max_length=50,
        description="e.g. '60% Female, 40% Male'")
    top_audience_countries:Optional[str] = Field(None, max_length=255,
        description="Comma-separated e.g. 'India,UAE,USA'")
    content_categories:    Optional[str] = Field(None, max_length=500)
    collab_types_offered:  Optional[str] = Field(None, max_length=500)
    rate_card_url:         Optional[str] = Field(None, max_length=500)


class CreatorStatsResponse(CreatorStatsCreate):
    id:           uuid.UUID
    portfolio_id: uuid.UUID
    model_config = {"from_attributes": True}


# ── Custom Fields ─────────────────────────────────────────────────────────────

class CustomFieldCreate(BaseModel):
    field_name:   str  = Field(..., min_length=1, max_length=100,
        description="e.g. 'Certified Personal Trainer'")
    field_value:  str  = Field(..., min_length=1, max_length=500,
        description="e.g. 'Yes — ACE certified since 2021'")
    is_public:    bool = True
    display_order:int  = Field(default=0, ge=0)


class CustomFieldResponse(BaseModel):
    id:            uuid.UUID
    portfolio_id:  uuid.UUID
    field_name:    str
    field_value:   str
    is_public:     bool
    display_order: int
    model_config = {"from_attributes": True}


# ── Portfolio Create / Update ─────────────────────────────────────────────────

class PortfolioCreate(BaseModel):
    display_name:      str              = Field(..., min_length=2, max_length=255,
        examples=["Riya Sharma"])
    tagline:           Optional[str]    = Field(None, max_length=500,
        examples=["Mumbai-based fashion model & lifestyle creator"])
    bio:               Optional[str]    = Field(None, max_length=3000)
    industry_type:     IndustryType     = Field(default=IndustryType.OTHER)
    city:              Optional[str]    = Field(None, max_length=100)
    state:             Optional[str]    = Field(None, max_length=100)
    country:           str              = Field(default="India", max_length=100)
    profile_image_url: Optional[str]    = Field(None, max_length=500)
    instagram_url:     Optional[str]    = Field(None, max_length=500)
    youtube_url:       Optional[str]    = Field(None, max_length=500)
    twitter_url:       Optional[str]    = Field(None, max_length=500)
    tiktok_url:        Optional[str]    = Field(None, max_length=500)
    website_url:       Optional[str]    = Field(None, max_length=500)


class PortfolioUpdate(BaseModel):
    display_name:      Optional[str]    = Field(None, min_length=2, max_length=255)
    tagline:           Optional[str]    = Field(None, max_length=500)
    bio:               Optional[str]    = Field(None, max_length=3000)
    industry_type:     Optional[IndustryType] = None
    city:              Optional[str]    = Field(None, max_length=100)
    state:             Optional[str]    = Field(None, max_length=100)
    profile_image_url: Optional[str]    = Field(None, max_length=500)
    instagram_url:     Optional[str]    = Field(None, max_length=500)
    youtube_url:       Optional[str]    = Field(None, max_length=500)
    twitter_url:       Optional[str]    = Field(None, max_length=500)
    tiktok_url:        Optional[str]    = Field(None, max_length=500)
    website_url:       Optional[str]    = Field(None, max_length=500)
    is_public:         Optional[bool]   = None


class PortfolioResponse(BaseModel):
    id:                uuid.UUID
    influencer_id:     uuid.UUID
    display_name:      str
    tagline:           Optional[str]
    bio:               Optional[str]
    industry_type:     IndustryType
    city:              Optional[str]
    state:             Optional[str]
    country:           str
    profile_image_url: Optional[str]
    instagram_url:     Optional[str]
    youtube_url:       Optional[str]
    twitter_url:       Optional[str]
    tiktok_url:        Optional[str]
    website_url:       Optional[str]
    pdf_url:           Optional[str]
    pdf_generated_at:  Optional[datetime]
    is_public:         bool
    is_published:      bool
    items:             List[PortfolioItemResponse]       = []
    physical_stats:    Optional[PhysicalStatsResponse]  = None
    creator_stats:     Optional[CreatorStatsResponse]   = None
    custom_fields:     List[CustomFieldResponse]        = []
    created_at:        datetime
    updated_at:        datetime
    model_config = {"from_attributes": True}


class PortfolioPublicResponse(BaseModel):
    """
    What brands and public users see — no private payment or
    contact info, but full portfolio content.
    """
    id:                uuid.UUID
    influencer_id:     uuid.UUID
    display_name:      str
    tagline:           Optional[str]
    bio:               Optional[str]
    industry_type:     IndustryType
    city:              Optional[str]
    state:             Optional[str]
    country:           str
    profile_image_url: Optional[str]
    instagram_url:     Optional[str]
    youtube_url:       Optional[str]
    tiktok_url:        Optional[str]
    website_url:       Optional[str]
    pdf_url:           Optional[str]
    items:             List[PortfolioItemResponse]      = []
    physical_stats:    Optional[PhysicalStatsResponse] = None
    creator_stats:     Optional[CreatorStatsResponse]  = None
    custom_fields:     List[CustomFieldResponse]       = []
    model_config = {"from_attributes": True}
