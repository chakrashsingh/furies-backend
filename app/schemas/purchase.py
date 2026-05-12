"""
app/schemas/purchase.py
────────────────────────
Schemas for Mock Purchase API + purchase history responses.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.purchase import PurchaseStatus


class MockPurchaseRequest(BaseModel):
    """
    Simulates a buyer completing a purchase.

    In a real system this payload arrives from a payment gateway webhook.
    Here we accept it directly from the client for testing.

    session_token ties this purchase to the originating affiliate click.
    If omitted, the purchase is still recorded but has no influencer attribution.
    """
    product_id:    uuid.UUID
    session_token: Optional[str] = Field(
        None,
        description="The aff_session token received on the redirect URL. "
                    "Required for commission attribution.",
        examples=["aB3k...43-char-token...mQ"],
    )
    buyer_name:  Optional[str]     = Field(None, max_length=255)
    buyer_email: Optional[EmailStr]= None
    quantity:    int               = Field(default=1, ge=1, le=100)

    # Optional override — if omitted, uses the product's current price
    override_amount: Optional[Decimal] = Field(
        None, gt=0,
        description="Override purchase amount (e.g. after coupon). "
                    "Defaults to product.price × quantity."
    )


class PurchaseResponse(BaseModel):
    """Returned after a successful mock purchase."""
    id:                uuid.UUID
    affiliate_link_id: Optional[uuid.UUID]
    click_id:          Optional[uuid.UUID]
    product_id:        Optional[uuid.UUID]
    purchase_amount:   Decimal
    commission_pct:    Decimal
    commission_amount: Decimal
    currency:          str
    buyer_name:        Optional[str]
    buyer_email:       Optional[str]
    order_id:          Optional[str]
    status:            PurchaseStatus
    purchased_at:      datetime

    # Computed summary — added in router
    influencer_id: Optional[uuid.UUID] = None
    attribution:   str = "none"   # "attributed" | "unattributed" | "none"

    model_config = {"from_attributes": True}


class PurchaseListItem(BaseModel):
    """Compact row for purchase history lists."""
    id:               uuid.UUID
    product_id:       Optional[uuid.UUID]
    purchase_amount:  Decimal
    commission_amount:Decimal
    status:           PurchaseStatus
    purchased_at:     datetime

    model_config = {"from_attributes": True}
