"""
app/schemas/application.py
───────────────────────────
Pydantic schemas for the Application system.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.application import ApplicationStatus, ApplicationType


class ApplicationCreate(BaseModel):
    """
    Influencer submits an application to a campaign or event.
    Exactly one of (campaign_id, event_id) must be provided.
    """
    campaign_id:    Optional[uuid.UUID] = None
    event_id:       Optional[uuid.UUID] = None
    cover_letter:   Optional[str]       = Field(None, max_length=3000,
        description="Why you're a great fit for this collab.")
    proposed_rate:  Optional[Decimal]   = Field(None, ge=0,
        description="Your proposed fee in INR (for paid collabs).")
    portfolio_url:  Optional[str]       = Field(None, max_length=500)


class ApplicationDecision(BaseModel):
    """
    Brand or event host accepts / rejects an application.
    """
    status: ApplicationStatus = Field(
        ...,
        description="Must be 'accepted' or 'rejected'.",
    )
    decision_note: Optional[str] = Field(None, max_length=1000,
        description="Optional message to the influencer explaining the decision.")


class ApplicationResponse(BaseModel):
    id:               uuid.UUID
    influencer_id:    uuid.UUID
    application_type: ApplicationType
    campaign_id:      Optional[uuid.UUID]
    event_id:         Optional[uuid.UUID]
    status:           ApplicationStatus
    cover_letter:     Optional[str]
    proposed_rate:    Optional[Decimal]
    portfolio_url:    Optional[str]
    decision_note:    Optional[str]
    decided_at:       Optional[datetime]
    applied_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class ApplicationSummary(BaseModel):
    """Compact row for list views."""
    id:               uuid.UUID
    influencer_id:    uuid.UUID
    application_type: ApplicationType
    campaign_id:      Optional[uuid.UUID]
    event_id:         Optional[uuid.UUID]
    status:           ApplicationStatus
    proposed_rate:    Optional[Decimal]
    applied_at:       datetime

    model_config = {"from_attributes": True}
