"""
app/models/portfolio.py
────────────────────────
Portfolio system for Furies platform.

Architecture:
    InfluencerProfile (1) ──── (1) Portfolio
    Portfolio         (1) ──── (many) PortfolioItem
    Portfolio         (1) ──── (many) PhysicalStats    (fashion/modelling)
    Portfolio         (1) ──── (1)  CreatorStats       (YouTuber/content)

Why separate stat tables?
    A fashion model needs height/weight/measurements.
    A YouTuber needs subscriber count/avg views.
    Forcing both into one table creates 15 nullable columns —
    instead each industry gets a clean dedicated table.

IndustryType drives:
    - Which stat fields are shown
    - Which PDF template is used
    - Which brand discovery filters apply
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class IndustryType(str, enum.Enum):
    FASHION          = "fashion"
    MODELLING        = "modelling"
    YOUTUBE          = "youtube"
    INSTAGRAM        = "instagram"
    PODCAST          = "podcast"
    FITNESS          = "fitness"
    FOOD_BEVERAGE    = "food_beverage"
    TRAVEL           = "travel"
    BEAUTY           = "beauty"
    TECH             = "tech"
    GAMING           = "gaming"
    EDUCATION        = "education"
    ENTERTAINMENT    = "entertainment"
    OTHER            = "other"


class SkinTone(str, enum.Enum):
    FAIR       = "fair"
    WHEATISH   = "wheatish"
    MEDIUM     = "medium"
    OLIVE      = "olive"
    DUSKY      = "dusky"
    DARK       = "dark"


class HairColor(str, enum.Enum):
    BLACK  = "black"
    BROWN  = "brown"
    BLONDE = "blonde"
    RED    = "red"
    GREY   = "grey"
    OTHER  = "other"


class EyeColor(str, enum.Enum):
    BLACK  = "black"
    BROWN  = "brown"
    HAZEL  = "hazel"
    GREEN  = "green"
    BLUE   = "blue"
    OTHER  = "other"


class Portfolio(Base):
    """
    Master portfolio record — one per influencer.
    Stores headline info + links to industry-specific stat tables.
    """
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("influencer_profiles.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    # ── Headline ──────────────────────────────────────────────────────────────
    display_name:  Mapped[str] = mapped_column(String(255), nullable=False)
    tagline:       Mapped[str] = mapped_column(String(500), nullable=True)
    bio:           Mapped[str] = mapped_column(Text,        nullable=True)
    industry_type: Mapped[IndustryType] = mapped_column(
        Enum(IndustryType, name="industry_type_enum"),
        nullable=False, default=IndustryType.OTHER, index=True,
    )

    # ── Location ──────────────────────────────────────────────────────────────
    city:    Mapped[str] = mapped_column(String(100), nullable=True)
    state:   Mapped[str] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)

    # ── Profile image ─────────────────────────────────────────────────────────
    profile_image_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # ── Social links ──────────────────────────────────────────────────────────
    instagram_url: Mapped[str] = mapped_column(String(500), nullable=True)
    youtube_url:   Mapped[str] = mapped_column(String(500), nullable=True)
    twitter_url:   Mapped[str] = mapped_column(String(500), nullable=True)
    tiktok_url:    Mapped[str] = mapped_column(String(500), nullable=True)
    website_url:   Mapped[str] = mapped_column(String(500), nullable=True)

    # ── PDF ───────────────────────────────────────────────────────────────────
    pdf_url:          Mapped[str] = mapped_column(String(500), nullable=True)
    pdf_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Visibility ────────────────────────────────────────────────────────────
    is_public:    Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    influencer     = relationship("InfluencerProfile", backref="portfolio",       lazy="selectin")
    items          = relationship("PortfolioItem",     back_populates="portfolio", lazy="selectin",
                                  cascade="all, delete-orphan")
    physical_stats = relationship("PhysicalStats",     back_populates="portfolio", lazy="selectin",
                                  uselist=False, cascade="all, delete-orphan")
    creator_stats  = relationship("CreatorStats",      back_populates="portfolio", lazy="selectin",
                                  uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Portfolio display_name={self.display_name!r} industry={self.industry_type}>"


class PortfolioItemType(str, enum.Enum):
    IMAGE       = "image"       # direct image URL (Instagram, hosted link)
    VIDEO_LINK  = "video_link"  # YouTube / Reels URL
    PDF         = "pdf"         # media kit or case study PDF link
    CASE_STUDY  = "case_study"  # text-based past collab description
    BRAND_COLLAB = "brand_collab" # past brand work with results


class PortfolioItem(Base):
    """
    One item in the portfolio — image, video link, case study, or brand collab.
    Ordered by display_order for the PDF and profile page.
    """
    __tablename__ = "portfolio_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    item_type:    Mapped[PortfolioItemType] = mapped_column(
        Enum(PortfolioItemType, name="portfolio_item_type_enum"), nullable=False
    )
    title:        Mapped[str] = mapped_column(String(255), nullable=True)
    description:  Mapped[str] = mapped_column(Text,        nullable=True)
    media_url:    Mapped[str] = mapped_column(String(500), nullable=True)  # image/video URL
    thumbnail_url:Mapped[str] = mapped_column(String(500), nullable=True)
    brand_name:   Mapped[str] = mapped_column(String(255), nullable=True)  # for brand_collab items
    results:      Mapped[str] = mapped_column(Text,        nullable=True)  # "Generated 50k views"
    display_order:Mapped[int] = mapped_column(Integer,     default=0, nullable=False)

    # For brand collab items — when it happened
    collab_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    portfolio = relationship("Portfolio", back_populates="items")

    def __repr__(self) -> str:
        return f"<PortfolioItem type={self.item_type} title={self.title!r}>"


class PhysicalStats(Base):
    """
    Fashion / modelling physical measurements.
    Only populated for industry_type = FASHION | MODELLING | FITNESS | BEAUTY etc.
    """
    __tablename__ = "physical_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    # ── Body measurements ─────────────────────────────────────────────────────
    height_cm:     Mapped[Optional[int]]     = mapped_column(Integer,        nullable=True)
    weight_kg:     Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1),  nullable=True)
    bust_cm:       Mapped[Optional[int]]     = mapped_column(Integer,        nullable=True)
    waist_cm:      Mapped[Optional[int]]     = mapped_column(Integer,        nullable=True)
    hips_cm:       Mapped[Optional[int]]     = mapped_column(Integer,        nullable=True)
    shoe_size_eu:  Mapped[Optional[int]]     = mapped_column(Integer,        nullable=True)
    dress_size:    Mapped[Optional[str]]     = mapped_column(String(10),     nullable=True)  # XS/S/M/L/XL

    # ── Physical appearance ───────────────────────────────────────────────────
    skin_tone:   Mapped[Optional[SkinTone]]   = mapped_column(
        Enum(SkinTone,   name="skin_tone_enum"),  nullable=True
    )
    hair_color:  Mapped[Optional[HairColor]]  = mapped_column(
        Enum(HairColor,  name="hair_color_enum"), nullable=True
    )
    eye_color:   Mapped[Optional[EyeColor]]   = mapped_column(
        Enum(EyeColor,   name="eye_color_enum"),  nullable=True
    )

    # ── Experience ────────────────────────────────────────────────────────────
    years_experience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    languages:        Mapped[str]           = mapped_column(String(255), nullable=True,
        comment="Comma-separated: 'Hindi,English,Marathi'")
    willing_to_travel: Mapped[bool]         = mapped_column(Boolean, default=True, nullable=False)

    portfolio = relationship("Portfolio", back_populates="physical_stats")


class CreatorStats(Base):
    """
    YouTuber / content creator platform statistics.
    Only populated for industry_type = YOUTUBE | INSTAGRAM | PODCAST | etc.
    """
    __tablename__ = "creator_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    # ── Primary platform stats ────────────────────────────────────────────────
    primary_platform:    Mapped[str]            = mapped_column(String(50),  nullable=True)
    subscriber_count:    Mapped[Optional[int]]  = mapped_column(Integer,     nullable=True)
    avg_views_per_video: Mapped[Optional[int]]  = mapped_column(Integer,     nullable=True)
    avg_likes_per_post:  Mapped[Optional[int]]  = mapped_column(Integer,     nullable=True)
    avg_comments:        Mapped[Optional[int]]  = mapped_column(Integer,     nullable=True)
    posting_frequency:   Mapped[Optional[str]]  = mapped_column(String(100), nullable=True,
        comment="e.g. '3 videos/week', 'Daily Stories'")

    # ── Audience breakdown ────────────────────────────────────────────────────
    audience_age_range:    Mapped[Optional[str]] = mapped_column(String(50),  nullable=True,
        comment="e.g. '18-24'")
    audience_gender_split: Mapped[Optional[str]] = mapped_column(String(50),  nullable=True,
        comment="e.g. '60% Female, 40% Male'")
    top_audience_countries:Mapped[Optional[str]] = mapped_column(String(255), nullable=True,
        comment="Comma-separated: 'India,UAE,USA'")

    # ── Content details ───────────────────────────────────────────────────────
    content_categories: Mapped[Optional[str]] = mapped_column(String(500), nullable=True,
        comment="Comma-separated content types")
    collab_types_offered: Mapped[Optional[str]] = mapped_column(String(500), nullable=True,
        comment="Dedicated video, Integration, Review, Shorts, Reels...")
    rate_card_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    portfolio = relationship("Portfolio", back_populates="creator_stats")


class CustomField(Base):
    """
    Industry-specific custom fields — anything not covered by physical/creator stats.
    Key-value pairs attached to a portfolio. Brands can filter on these too.

    Examples:
        industry=fitness → "Certified Personal Trainer: Yes", "Specialization: Calisthenics"
        industry=food    → "Cuisine Type: South Indian", "Has Food Photography Studio: Yes"
        industry=travel  → "Countries Visited: 42", "Visa Types: Schengen, US, UK"
    """
    __tablename__ = "custom_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    field_name:  Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str] = mapped_column(String(500), nullable=False)
    is_public:   Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    portfolio = relationship("Portfolio", backref="custom_fields",
                             foreign_keys=[portfolio_id])
