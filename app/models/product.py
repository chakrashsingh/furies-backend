"""
app/models/product.py
──────────────────────
Product / Service that a Brand lists on the platform.

Relationships:
    BrandProfile (1) ──── (many) Product
    Product      (1) ──── (many) AffiliateLink   ← Step 5
    Product      (1) ──── (many) Purchase         ← Step 7

Design notes:
    - commission_pct stored as Numeric(5,2): supports 0.00 – 100.00
    - is_active allows soft-delete (products with existing affiliate links
      should never be hard-deleted — that breaks click/conversion history)
    - ProductType enum lets the platform handle physical products vs
      digital downloads vs services differently in future
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey,
    Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class ProductType(str, enum.Enum):
    PHYSICAL = "physical"
    DIGITAL  = "digital"
    SERVICE  = "service"


class Product(Base):
    __tablename__ = "products"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core fields ───────────────────────────────────────────────────────────
    name: Mapped[str]         = mapped_column(String(255), nullable=False)
    description: Mapped[str]  = mapped_column(Text,        nullable=True)
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, name="product_type_enum"),
        nullable=False,
        default=ProductType.PHYSICAL,
    )
    image_url: Mapped[str]    = mapped_column(String(500), nullable=True)
    product_url: Mapped[str]  = mapped_column(String(500), nullable=True)  # landing page

    # ── Pricing ───────────────────────────────────────────────────────────────
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False              # e.g. ₹1299.00
    )
    currency: Mapped[str]  = mapped_column(String(3), default="INR", nullable=False)

    # ── Affiliate commission ──────────────────────────────────────────────────
    commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("10.00")   # 10% default
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    brand = relationship("BrandProfile", back_populates="products", lazy="selectin")
    # affiliate_links = relationship("AffiliateLink", back_populates="product")  ← Step 5
    # purchases       = relationship("Purchase",      back_populates="product")  ← Step 7

    def __repr__(self) -> str:
        return f"<Product name={self.name!r} price={self.price} commission={self.commission_pct}%>"
