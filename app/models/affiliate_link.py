"""
app/models/affiliate_link.py
─────────────────────────────
Affiliate link — the core tracking unit of the platform.

When an influencer promotes a product, they generate a unique short code.
Every visit to /go/<code> increments the click counter and redirects
to the product URL. A purchase made through that session is attributed
to the influencer (Step 7).

Relationships:
    InfluencerProfile (1) ──── (many) AffiliateLink
    Product           (1) ──── (many) AffiliateLink
    AffiliateLink     (1) ──── (many) Click            ← Step 6
    AffiliateLink     (1) ──── (many) Purchase          ← Step 7

Design notes:
    - `short_code` is the public-facing identifier (e.g. "aB3kZ9").
      Generated using secrets.token_urlsafe, truncated to 8 chars.
    - Click / conversion counts are denormalised here for O(1) dashboard
      reads. The canonical source of truth is the Click / Purchase tables.
    - is_active allows an influencer to pause a link without losing history.
    - custom_alias allows vanity URLs (e.g. "riya-vitc") — unique per platform.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    Numeric, String, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AffiliateLink(Base):
    __tablename__ = "affiliate_links"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("influencer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Short link ────────────────────────────────────────────────────────────
    short_code: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False, index=True
    )
    custom_alias: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=True, index=True
    )

    # ── Denormalised counters (updated on each click / purchase) ──────────────
    click_count:      Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Earnings snapshot (updated when purchase is recorded) ─────────────────
    total_earned: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
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
    influencer = relationship("InfluencerProfile", backref="affiliate_links", lazy="selectin")
    product    = relationship("Product",           backref="affiliate_links", lazy="selectin")
    clicks     = relationship("Click",    back_populates="affiliate_link", lazy="dynamic")
    purchases  = relationship("Purchase", back_populates="affiliate_link", lazy="dynamic")

    # ── Constraints ───────────────────────────────────────────────────────────
    __table_args__ = (
        # One influencer can only have one active link per product
        UniqueConstraint("influencer_id", "product_id", name="uq_influencer_product_link"),
    )

    def __repr__(self) -> str:
        return (
            f"<AffiliateLink code={self.short_code!r} "
            f"clicks={self.click_count} conversions={self.conversion_count}>"
        )
