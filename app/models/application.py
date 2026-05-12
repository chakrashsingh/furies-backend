"""
app/models/application.py
──────────────────────────
Universal application model — influencers apply to both campaigns and events
through this single table. One of (campaign_id, event_id) is always set,
never both (enforced at service layer with a CHECK-style guard).

Why one table not two?
    - Application lifecycle (pending → accepted/rejected) is identical.
    - Influencer dashboard shows all applications in one unified view.
    - Analytics can aggregate across both types cleanly.

Relationships:
    InfluencerProfile (1) ──── (many) Application
    Campaign          (1) ──── (many) Application
    Event             (1) ──── (many) Application

States:
    PENDING   — submitted, awaiting brand/host decision
    ACCEPTED  — brand/host approved; collab confirmed
    REJECTED  — brand/host declined
    WITHDRAWN — influencer cancelled their own application
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint, DateTime, Enum,
    ForeignKey, Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class ApplicationStatus(str, enum.Enum):
    PENDING   = "pending"
    ACCEPTED  = "accepted"
    REJECTED  = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationType(str, enum.Enum):
    CAMPAIGN = "campaign"
    EVENT    = "event"


class Application(Base):
    __tablename__ = "applications"

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

    # ── Target (one of these is set, not both) ────────────────────────────────
    application_type: Mapped[ApplicationType] = mapped_column(
        Enum(ApplicationType, name="application_type_enum"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status_enum"),
        nullable=False,
        default=ApplicationStatus.PENDING,
        index=True,
    )

    # ── Influencer pitch ──────────────────────────────────────────────────────
    cover_letter: Mapped[str] = mapped_column(Text, nullable=True)
    proposed_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True,
        comment="Influencer's proposed fee (INR). Only relevant for paid collabs."
    )
    portfolio_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # ── Decision (set by brand / host on accept/reject) ───────────────────────
    decision_note: Mapped[str] = mapped_column(Text, nullable=True,
        comment="Feedback from the brand/host on accept or rejection")
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    applied_at: Mapped[datetime] = mapped_column(
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
    influencer  = relationship("InfluencerProfile", backref="applications",  lazy="selectin")
    campaign    = relationship("Campaign",           back_populates="applications", lazy="selectin")
    event       = relationship("Event",              back_populates="applications", lazy="selectin")
    decided_by  = relationship("User", foreign_keys=[decided_by_user_id],    lazy="selectin")

    # ── DB-level constraint: exactly one of campaign_id / event_id must be set ─
    __table_args__ = (
        CheckConstraint(
            "(campaign_id IS NOT NULL AND event_id IS NULL) OR "
            "(campaign_id IS NULL AND event_id IS NOT NULL)",
            name="ck_application_target_exclusive",
        ),
    )

    def __repr__(self) -> str:
        target = f"campaign={self.campaign_id}" if self.campaign_id else f"event={self.event_id}"
        return f"<Application {target} influencer={self.influencer_id} status={self.status}>"
