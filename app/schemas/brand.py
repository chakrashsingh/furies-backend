"""
app/schemas/brand.py
─────────────────────
Pydantic schemas for BrandProfile CRUD.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from app.models.brand import IndustryCategory


class BrandProfileCreate(BaseModel):
    company_name:    str               = Field(..., min_length=2, max_length=255)
    company_website: Optional[str]     = Field(None, max_length=500)
    industry: IndustryCategory         = Field(default=IndustryCategory.OTHER)
    description: Optional[str]         = Field(None, max_length=2000)
    logo_url:    Optional[str]         = Field(None, max_length=500)
    contact_email: Optional[str]       = Field(None, max_length=255)
    contact_phone: Optional[str]       = Field(None, max_length=20)
    gst_number:    Optional[str]       = Field(None, max_length=20)


class BrandProfileUpdate(BaseModel):
    """All optional — PATCH semantics."""
    company_name:    Optional[str]     = Field(None, min_length=2, max_length=255)
    company_website: Optional[str]     = Field(None, max_length=500)
    industry: Optional[IndustryCategory] = None
    description: Optional[str]         = Field(None, max_length=2000)
    logo_url:    Optional[str]         = Field(None, max_length=500)
    contact_email: Optional[str]       = Field(None, max_length=255)
    contact_phone: Optional[str]       = Field(None, max_length=20)
    gst_number:    Optional[str]       = Field(None, max_length=20)


class BrandProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    company_name: str
    company_website: Optional[str]
    industry: IndustryCategory
    description: Optional[str]
    logo_url: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
