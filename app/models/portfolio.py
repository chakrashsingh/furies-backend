import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base

class IndustryType(str, enum.Enum):
    FASHION       = "fashion"
    MODELLING     = "modelling"
    YOUTUBE       = "youtube"
    INSTAGRAM     = "instagram"
    FITNESS       = "fitness"
    FOOD          = "food"
    TRAVEL        = "travel"
    BEAUTY        = "beauty"
    TECH          = "tech"
    GAMING        = "gaming"
    EDUCATION     = "education"
    OTHER         = "other"

class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[str] = mapped_column(String(500), nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    industry_type: Mapped[IndustryType] = mapped_column(Enum(IndustryType, name="industry_type_enum"), default=IndustryType.OTHER)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    profile_image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    instagram_url: Mapped[str] = mapped_column(String(500), nullable=True)
    youtube_url: Mapped[str] = mapped_column(String(500), nullable=True)
    twitter_url: Mapped[str] = mapped_column(String(500), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user = relationship("User", backref="portfolio")
    items = relationship("PortfolioItem", back_populates="portfolio", cascade="all, delete-orphan")
    physical_stats = relationship("PhysicalStats", back_populates="portfolio", uselist=False, cascade="all, delete-orphan")

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    media_url: Mapped[str] = mapped_column(String(500), nullable=True)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=True)
    results: Mapped[str] = mapped_column(String(500), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    portfolio = relationship("Portfolio", back_populates="items")

class PhysicalStats(Base):
    __tablename__ = "physical_stats"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), unique=True, nullable=False)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[str] = mapped_column(String(10), nullable=True)
    bust_cm: Mapped[int] = mapped_column(Integer, nullable=True)
    waist_cm: Mapped[int] = mapped_column(Integer, nullable=True)
    hips_cm: Mapped[int] = mapped_column(Integer, nullable=True)
    shoe_size: Mapped[str] = mapped_column(String(10), nullable=True)
    dress_size: Mapped[str] = mapped_column(String(10), nullable=True)
    skin_tone: Mapped[str] = mapped_column(String(50), nullable=True)
    hair_color: Mapped[str] = mapped_column(String(50), nullable=True)
    eye_color: Mapped[str] = mapped_column(String(50), nullable=True)
    languages: Mapped[str] = mapped_column(String(255), nullable=True)
    willing_to_travel: Mapped[bool] = mapped_column(Boolean, default=True)
    portfolio = relationship("Portfolio", back_populates="physical_stats")
