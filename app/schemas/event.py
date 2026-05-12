"""
app/schemas/event.py
─────────────────────
Pydantic schemas for Event CRUD + listing.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.event import EventCategory, EventCollab, EventStatus


class EventCreate(BaseModel):
    title: str                    = Field(..., min_length=3, max_length=255,
                                          examples=["Sharma Wedding Reception"])
    description: Optional[str]    = Field(None, max_length=5000)
    event_category: EventCategory = Field(default=EventCategory.OTHER)
    collab_type: EventCollab      = Field(default=EventCollab.PAID)
    location_city:    Optional[str] = Field(None, max_length=100, examples=["Mumbai"])
    location_state:   Optional[str] = Field(None, max_length=100, examples=["Maharashtra"])
    location_country: str           = Field(default="India", max_length=100)
    location_venue:   Optional[str] = Field(None, max_length=255)
    is_virtual: bool                = Field(default=False)
    budget_min: Optional[Decimal]   = Field(None, ge=0, examples=[Decimal("5000.00")])
    budget_max: Optional[Decimal]   = Field(None, ge=0, examples=[Decimal("20000.00")])
    currency: str                   = Field(default="INR", min_length=3, max_length=3)
    required_niches:  Optional[str] = Field(None, max_length=500,
        description="Comma-separated niches. e.g. 'fashion,lifestyle'")
    min_followers:    int           = Field(default=0, ge=0)
    influencers_needed: int         = Field(default=1, ge=1)
    deliverables: Optional[str]     = Field(None, max_length=2000)
    application_deadline: Optional[datetime] = None
    event_date:      Optional[datetime]      = None
    banner_url:      Optional[str]           = Field(None, max_length=500)


class EventUpdate(BaseModel):
    """All optional — PATCH semantics."""
    title: Optional[str]            = Field(None, min_length=3, max_length=255)
    description: Optional[str]      = Field(None, max_length=5000)
    event_category: Optional[EventCategory] = None
    collab_type: Optional[EventCollab]      = None
    status: Optional[EventStatus]           = None
    location_city:    Optional[str]         = Field(None, max_length=100)
    location_state:   Optional[str]         = Field(None, max_length=100)
    location_venue:   Optional[str]         = Field(None, max_length=255)
    is_virtual: Optional[bool]              = None
    budget_min: Optional[Decimal]           = Field(None, ge=0)
    budget_max: Optional[Decimal]           = Field(None, ge=0)
    required_niches:  Optional[str]         = Field(None, max_length=500)
    min_followers:    Optional[int]         = Field(None, ge=0)
    influencers_needed: Optional[int]       = Field(None, ge=1)
    deliverables: Optional[str]             = Field(None, max_length=2000)
    application_deadline: Optional[datetime] = None
    event_date:      Optional[datetime]     = None
    banner_url:      Optional[str]          = Field(None, max_length=500)


class EventResponse(BaseModel):
    id:                   uuid.UUID
    posted_by_user_id:    uuid.UUID
    title:                str
    description:          Optional[str]
    event_category:       EventCategory
    collab_type:          EventCollab
    status:               EventStatus
    location_city:        Optional[str]
    location_state:       Optional[str]
    location_country:     str
    location_venue:       Optional[str]
    is_virtual:           bool
    budget_min:           Optional[Decimal]
    budget_max:           Optional[Decimal]
    currency:             str
    required_niches:      Optional[str]
    min_followers:        int
    influencers_needed:   int
    deliverables:         Optional[str]
    application_deadline: Optional[datetime]
    event_date:           Optional[datetime]
    banner_url:           Optional[str]
    created_at:           datetime
    updated_at:           datetime

    model_config = {"from_attributes": True}


class EventSummary(BaseModel):
    """Compact card for directory listings."""
    id:             uuid.UUID
    title:          str
    event_category: EventCategory
    collab_type:    EventCollab
    status:         EventStatus
    location_city:  Optional[str]
    budget_min:     Optional[Decimal]
    budget_max:     Optional[Decimal]
    min_followers:  int
    event_date:     Optional[datetime]
    created_at:     datetime

    model_config = {"from_attributes": True}
