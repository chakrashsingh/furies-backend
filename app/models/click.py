"""
app/models/click.py
────────────────────
Immutable click event — one row per visit to /go/<code>.

Kept intentionally lightweight. Every field is set at write time and
never updated — this is an append-only audit log, not a mutable record.

Relationships:
    AffiliateLink (1) ──── (many) Click

Fields captured per click:
    - ip_address    — for dedup / fraud detection (hashed in production)
    - user_agent    — device/browser for analytics breakdown
    - referrer      — where the traffic came from
    - session_token — random token tied to this visit; used to match
                      a subsequent purchase back to this click (Step 7)
    - is_unique     — False if same ip+link seen within 24 hours (dedup)
    - converted     — flipped to True when a Purchase is recorded for
                      the same session_token (Step 7)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    affiliate_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Request metadata ──────────────────────────────────────────────────────
    ip_address:    Mapped[str] = mapped_column(String(45),  nullable=True)  # IPv4/IPv6
    user_agent:    Mapped[str] = mapped_column(Text,        nullable=True)
    referrer:      Mapped[str] = mapped_column(String(500), nullable=True)

    # ── Session token — bridges click → purchase ──────────────────────────────
    session_token: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )

    # ── Dedup / conversion flags ──────────────────────────────────────────────
    is_unique:  Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    converted:  Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Timestamp (immutable) ─────────────────────────────────────────────────
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    affiliate_link = relationship("AffiliateLink", back_populates="clicks")

    def __repr__(self) -> str:
        return (
            f"<Click link={self.affiliate_link_id} "
            f"unique={self.is_unique} converted={self.converted}>"
        )
