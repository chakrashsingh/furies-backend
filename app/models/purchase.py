"""
app/models/purchase.py
───────────────────────
Purchase event — records a completed transaction attributed to an affiliate link.

Design:
    - Created by the mock purchase API (Step 7).
    - In production this would be triggered by a real payment webhook
      (Razorpay / Stripe) after payment confirmation.
    - Links back to a Click via session_token — that's how we know
      which influencer gets the commission.
    - commission_amount is pre-calculated at write time:
        commission_amount = purchase_amount * (commission_pct / 100)
    - status tracks the purchase lifecycle (pending → confirmed → paid).
      "paid" means the influencer has been paid out (Step 8 logic).

Relationships:
    AffiliateLink (1) ──── (many) Purchase
    Click         (1) ──── (0..1) Purchase    (one click → at most one purchase)
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class PurchaseStatus(str, enum.Enum):
    PENDING   = "pending"     # recorded, awaiting payment confirmation
    CONFIRMED = "confirmed"   # payment confirmed, commission owed
    PAID      = "paid"        # influencer paid out (future payout system)
    REFUNDED  = "refunded"    # purchase refunded, commission reversed


class Purchase(Base):
    __tablename__ = "purchases"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    affiliate_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_links.id", ondelete="SET NULL"),
        nullable=True,      # nullable: link may be deleted later, keep purchase record
        index=True,
    )
    click_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clicks.id", ondelete="SET NULL"),
        nullable=True,      # nullable: direct purchases (no click) are possible
        index=True,
    )

    # ── Session token (ties purchase to originating click) ────────────────────
    session_token: Mapped[str] = mapped_column(
        String(64), nullable=True, index=True
    )

    # ── Financial fields ──────────────────────────────────────────────────────
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purchase_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False    # full product price paid
    )
    commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False     # snapshot of % at time of purchase
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False    # pre-calculated: amount * pct / 100
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # ── Buyer info (mock — in production from payment gateway) ────────────────
    buyer_name:  Mapped[str] = mapped_column(String(255), nullable=True)
    buyer_email: Mapped[str] = mapped_column(String(255), nullable=True)
    order_id:    Mapped[str] = mapped_column(
        String(100), nullable=True, index=True   # external order reference
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status_enum"),
        default=PurchaseStatus.CONFIRMED,    # mock API confirms immediately
        nullable=False,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    affiliate_link = relationship("AffiliateLink", back_populates="purchases")
    click          = relationship("Click",    foreign_keys=[click_id])
    product        = relationship("Product",  foreign_keys=[product_id], lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<Purchase id={self.id} amount={self.purchase_amount} "
            f"commission={self.commission_amount} status={self.status}>"
        )
