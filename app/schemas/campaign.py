"""
app/schemas/campaign.py
────────────────────────
Pydantic schemas for Campaign CRUD + listing.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.campaign import CampaignStatus, CampaignType


class CampaignCreate(BaseModel):
    title: str              = Field(..., min_length=3, max_length=255,
                                    examples=["Summer Skincare Campaign 2025"])
    description: Optional[str] = Field(None, max_length=5000)
    campaign_type: CampaignType = Field(default=CampaignType.PAID)
    budget_amount: Optional[Decimal] = Field(None, gt=0,
                                             examples=[Decimal("25000.00")])
    currency: str           = Field(default="INR", min_length=3, max_length=3)
    target_niches: Optional[str] = Field(
        None, max_length=500,
        description="Comma-separated niches. e.g. 'fashion,beauty,lifestyle'",
        examples=["beauty,lifestyle"],
    )
    min_followers:    int   = Field(default=0, ge=0)
    max_influencers: Optional[int] = Field(None, ge=1)
    deliverables: Optional[str]    = Field(None, max_length=2000)
    application_deadline: Optional[datetime] = None
    campaign_start: Optional[datetime] = None
    campaign_end:   Optional[datetime] = None
    banner_url: Optional[str]      = Field(None, max_length=500)


class CampaignUpdate(BaseModel):
    """All optional — PATCH semantics."""
    title: Optional[str]          = Field(None, min_length=3, max_length=255)
    description: Optional[str]    = Field(None, max_length=5000)
    campaign_type: Optional[CampaignType] = None
    status: Optional[CampaignStatus]      = None
    budget_amount: Optional[Decimal]      = Field(None, gt=0)
    target_niches: Optional[str]          = Field(None, max_length=500)
    min_followers: Optional[int]          = Field(None, ge=0)
    max_influencers: Optional[int]        = Field(None, ge=1)
    deliverables: Optional[str]           = Field(None, max_length=2000)
    application_deadline: Optional[datetime] = None
    campaign_start: Optional[datetime]    = None
    campaign_end:   Optional[datetime]    = None
    banner_url: Optional[str]             = Field(None, max_length=500)


class CampaignResponse(BaseModel):
    id:               uuid.UUID
    brand_id:         uuid.UUID
    title:            str
    description:      Optional[str]
    campaign_type:    CampaignType
    status:           CampaignStatus
    budget_amount:    Optional[Decimal]
    currency:         str
    target_niches:    Optional[str]
    min_followers:    int
    max_influencers:  Optional[int]
    deliverables:     Optional[str]
    application_deadline: Optional[datetime]
    campaign_start:   Optional[datetime]
    campaign_end:     Optional[datetime]
    banner_url:       Optional[str]
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class CampaignSummary(BaseModel):
    """Compact card used in listing views."""
    id:            uuid.UUID
    brand_id:      uuid.UUID
    title:         str
    campaign_type: CampaignType
    status:        CampaignStatus
    budget_amount: Optional[Decimal]
    target_niches: Optional[str]
    min_followers: int
    application_deadline: Optional[datetime]
    created_at:    datetime

    model_config = {"from_attributes": True}
