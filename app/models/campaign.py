import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base

class CampaignStatus(str, enum.Enum):
    DRAFT     = "draft"
    OPEN      = "open"
    CLOSED    = "closed"
    COMPLETED = "completed"

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    budget: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=True)
    commission_pct: Mapped[Decimal] = mapped_column(Numeric(5,2), default=10)
    target_niche: Mapped[str] = mapped_column(String(100), nullable=True)
    min_followers: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus, name="campaign_status_enum"), default=CampaignStatus.OPEN)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    brand = relationship("BrandProfile", backref="campaigns")
    applications = relationship("Application", back_populates="campaign")

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    influencer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("influencer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    cover_letter: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    campaign = relationship("Campaign", back_populates="applications")
    influencer = relationship("InfluencerProfile", backref="applications")
