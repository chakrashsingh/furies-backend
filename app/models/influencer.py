import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base

class Niche(str, enum.Enum):
    FASHION       = "fashion"
    BEAUTY        = "beauty"
    TECH          = "tech"
    FOOD          = "food"
    TRAVEL        = "travel"
    FITNESS       = "fitness"
    LIFESTYLE     = "lifestyle"
    FINANCE       = "finance"
    GAMING        = "gaming"
    EDUCATION     = "education"
    ENTERTAINMENT = "entertainment"
    OTHER         = "other"

class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    niche: Mapped[Niche] = mapped_column(Enum(Niche, name="niche_enum"), default=Niche.OTHER)
    instagram_handle: Mapped[str] = mapped_column(String(100), nullable=True)
    youtube_channel: Mapped[str] = mapped_column(String(255), nullable=True)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement_rate: Mapped[Decimal] = mapped_column(Numeric(5,2), default=0)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    profile_image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    upi_id: Mapped[str] = mapped_column(String(100), nullable=True)
    total_earnings: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    total_clicks: Mapped[int] = mapped_column(Integer, default=0)
    total_conversions: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("User", backref="influencer_profile")
