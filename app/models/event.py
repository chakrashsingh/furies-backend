"""
app/models/event.py
────────────────────
Event hiring system — normal users (event hosts) and organizers
post events and hire influencers to attend / promote.

Two use cases captured in one model:
    1. Private events  — wedding, party, function, corporate event.
       A normal User (role=user) posts the event and its budget.
    2. Organizer collabs — professional event organizers post paid/unpaid
       invites. An Organizer is still role=user but their events have
       event_category = ORGANIZER_COLLAB.

Influencers browse open events and submit Applications (Step 11).

Relationships:
    User         (1) ──── (many) Event           (posted_by_user_id)
    Event        (1) ──── (many) Application      ← Step 11
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime, Enum, ForeignKey,
    Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class EventCategory(str, enum.Enum):
    WEDDING          = "wedding"
    BIRTHDAY_PARTY   = "birthday_party"
    CORPORATE        = "corporate"
    PRODUCT_LAUNCH   = "product_launch"
    MUSIC_FESTIVAL   = "music_festival"
    SPORTS           = "sports"
    CHARITY          = "charity"
    ORGANIZER_COLLAB = "organizer_collab"   # professional organizer posting
    OTHER            = "other"


class EventStatus(str, enum.Enum):
    OPEN      = "open"       # accepting influencer applications
    FILLED    = "filled"     # enough influencers hired
    COMPLETED = "completed"  # event happened
    CANCELLED = "cancelled"


class EventCollab(str, enum.Enum):
    PAID   = "paid"
    UNPAID = "unpaid"   # invitation only / exposure / gifting


class Event(Base):
    __tablename__ = "events"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    posted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Event details ─────────────────────────────────────────────────────────
    title: Mapped[str]        = mapped_column(String(255), nullable=False)
    description: Mapped[str]  = mapped_column(Text, nullable=True)
    event_category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="event_category_enum"),
        nullable=False,
        default=EventCategory.OTHER,
        index=True,
    )
    collab_type: Mapped[EventCollab] = mapped_column(
        Enum(EventCollab, name="event_collab_enum"),
        nullable=False,
        default=EventCollab.PAID,
    )
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status_enum"),
        nullable=False,
        default=EventStatus.OPEN,
        index=True,
    )

    # ── Location ──────────────────────────────────────────────────────────────
    location_city:    Mapped[str] = mapped_column(String(100), nullable=True)
    location_state:   Mapped[str] = mapped_column(String(100), nullable=True)
    location_country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    location_venue:   Mapped[str] = mapped_column(String(255), nullable=True)
    is_virtual:       Mapped[bool] = mapped_column(
        # covers virtual events / online collabs
        __import__("sqlalchemy").Boolean, default=False, nullable=False
    )

    # ── Budget ────────────────────────────────────────────────────────────────
    budget_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency:   Mapped[str]              = mapped_column(String(3), default="INR")

    # ── Influencer requirements ───────────────────────────────────────────────
    required_niches:  Mapped[str] = mapped_column(String(500), nullable=True,
        comment="Comma-separated niches the host prefers")
    min_followers:    Mapped[int] = mapped_column(__import__("sqlalchemy").Integer,
        default=0, nullable=False)
    influencers_needed: Mapped[int] = mapped_column(__import__("sqlalchemy").Integer,
        default=1, nullable=False)

    # ── Deliverables ──────────────────────────────────────────────────────────
    deliverables:          Mapped[str] = mapped_column(Text, nullable=True)
    application_deadline:  Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_date:            Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ── Media ─────────────────────────────────────────────────────────────────
    banner_url: Mapped[str] = mapped_column(String(500), nullable=True)

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
    posted_by    = relationship("User",        backref="events",         lazy="selectin")
    applications = relationship("Application", back_populates="event",   lazy="dynamic")

    def __repr__(self) -> str:
        return (
            f"<Event title={self.title!r} category={self.event_category} "
            f"status={self.status}>"
        )
