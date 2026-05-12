"""
app/schemas/affiliate_link.py
──────────────────────────────
Pydantic schemas for AffiliateLink CRUD + redirect response.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AffiliateLinkCreate(BaseModel):
    """
    Influencer creates a link for a specific product.
    custom_alias is optional — if omitted, a random short_code is used.
    """
    product_id: uuid.UUID
    custom_alias: Optional[str] = Field(
        None,
        min_length=3,
        max_length=60,
        pattern=r"^[a-zA-Z0-9_-]+$",        # URL-safe characters only
        description="Vanity alias, e.g. 'riya-vitc'. Letters, digits, - _ only.",
        examples=["riya-vitc-serum"],
    )

    @field_validator("custom_alias")
    @classmethod
    def lowercase_alias(cls, v: Optional[str]) -> Optional[str]:
        return v.lower() if v else v


class AffiliateLinkResponse(BaseModel):
    """
    Full link detail returned to the owning influencer.
    Includes performance counters and earnings.
    """
    id:             uuid.UUID
    influencer_id:  uuid.UUID
    product_id:     uuid.UUID
    short_code:     str
    custom_alias:   Optional[str]
    click_count:    int
    conversion_count: int
    total_earned:   Decimal
    is_active:      bool
    created_at:     datetime

    # Computed field — resolved in the router using request base URL
    redirect_url:   Optional[str] = None

    model_config = {"from_attributes": True}


class AffiliateLinkPublic(BaseModel):
    """
    Minimal info returned on redirect (non-sensitive).
    Used internally by the click-tracking endpoint.
    """
    id:          uuid.UUID
    short_code:  str
    product_url: Optional[str]   # the destination URL from Product.product_url
    is_active:   bool

    model_config = {"from_attributes": True}


class AffiliateLinkToggle(BaseModel):
    """PATCH body to pause / reactivate a link."""
    is_active: bool
