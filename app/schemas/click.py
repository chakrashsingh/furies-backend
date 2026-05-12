"""
app/schemas/click.py
─────────────────────
Schemas for click events and redirect responses.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClickResponse(BaseModel):
    """What we return from the redirect endpoint (informational)."""
    click_id:      uuid.UUID
    session_token: str
    is_unique:     bool
    redirect_to:   str           # the product destination URL


class ClickStats(BaseModel):
    """Aggregated click stats for a single affiliate link."""
    affiliate_link_id: uuid.UUID
    total_clicks:  int
    unique_clicks: int
    conversions:   int
    conversion_rate: float       # conversions / unique_clicks * 100


class ClickDetail(BaseModel):
    """Full click record — for influencer analytics view."""
    id:                uuid.UUID
    affiliate_link_id: uuid.UUID
    session_token:     str
    ip_address:        Optional[str]
    referrer:          Optional[str]
    is_unique:         bool
    converted:         bool
    clicked_at:        datetime

    model_config = {"from_attributes": True}
