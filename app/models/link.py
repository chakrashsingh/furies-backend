import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class AffiliateLink(Base):
    __tablename__ = "affiliate_links"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    cuelinks_url: Mapped[str] = mapped_column(Text, nullable=True)
    short_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    product_title: Mapped[str] = mapped_column(String(500), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=True)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5,2), default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)
    total_earned: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("User", backref="affiliate_links")

class Click(Base):
    __tablename__ = "clicks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("affiliate_links.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    link = relationship("AffiliateLink", backref="clicks")
