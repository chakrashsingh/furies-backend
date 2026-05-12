"""
app/schemas/product.py
───────────────────────
Pydantic schemas for Product CRUD + public listing.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.product import ProductType


class ProductCreate(BaseModel):
    name: str                  = Field(..., min_length=2, max_length=255,
                                       examples=["Vitamin C Serum 30ml"])
    description: Optional[str] = Field(None, max_length=5000)
    product_type: ProductType  = Field(default=ProductType.PHYSICAL)
    image_url:    Optional[str]= Field(None, max_length=500)
    product_url:  Optional[str]= Field(None, max_length=500)
    price: Decimal             = Field(..., gt=0, examples=[Decimal("999.00")])
    currency: str              = Field(default="INR", min_length=3, max_length=3)
    commission_pct: Decimal    = Field(
        default=Decimal("10.00"), ge=Decimal("0"), le=Decimal("100"),
        description="Commission percentage paid to influencer (0–100)",
        examples=[Decimal("15.00")],
    )


class ProductUpdate(BaseModel):
    """All optional — PATCH semantics."""
    name: Optional[str]            = Field(None, min_length=2, max_length=255)
    description: Optional[str]     = Field(None, max_length=5000)
    product_type: Optional[ProductType] = None
    image_url:    Optional[str]    = Field(None, max_length=500)
    product_url:  Optional[str]    = Field(None, max_length=500)
    price: Optional[Decimal]       = Field(None, gt=0)
    currency: Optional[str]        = Field(None, min_length=3, max_length=3)
    commission_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    is_active: Optional[bool]      = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    description: Optional[str]
    product_type: ProductType
    image_url: Optional[str]
    product_url: Optional[str]
    price: Decimal
    currency: str
    commission_pct: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
