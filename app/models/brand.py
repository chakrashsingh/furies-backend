import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base

class Industry(str, enum.Enum):
    FASHION      = "fashion"
    BEAUTY       = "beauty"
    TECH         = "tech"
    FOOD         = "food"
    FITNESS      = "fitness"
    FINANCE      = "finance"
    EDUCATION    = "education"
    OTHER        = "other"

class BrandProfile(Base):
    __tablename__ = "brand_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Industry] = mapped_column(Enum(Industry, name="industry_enum"), default=Industry.OTHER)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    website: Mapped[str] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("User", backref="brand_profile")
