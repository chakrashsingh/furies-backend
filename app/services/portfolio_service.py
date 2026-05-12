"""
app/services/portfolio_service.py
───────────────────────────────────
Business logic for Portfolio CRUD, PDF generation, and brand discovery.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import (
    CustomField, Portfolio, PortfolioItem,
    PhysicalStats, CreatorStats, IndustryType,
)
from app.models.influencer import InfluencerProfile
from app.models.user import User
from app.schemas.portfolio import (
    CustomFieldCreate, PhysicalStatsCreate, CreatorStatsCreate,
    PortfolioCreate, PortfolioItemCreate, PortfolioUpdate,
)


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_portfolio_by_influencer(
    db: AsyncSession, influencer_id: uuid.UUID
) -> Optional[Portfolio]:
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.influencer_id == influencer_id)
        .options(
            selectinload(Portfolio.items),
            selectinload(Portfolio.physical_stats),
            selectinload(Portfolio.creator_stats),
            selectinload(Portfolio.custom_fields),
        )
    )
    return result.scalar_one_or_none()


async def get_portfolio_by_id(
    db: AsyncSession, portfolio_id: uuid.UUID
) -> Optional[Portfolio]:
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.id == portfolio_id)
        .options(
            selectinload(Portfolio.items),
            selectinload(Portfolio.physical_stats),
            selectinload(Portfolio.creator_stats),
            selectinload(Portfolio.custom_fields),
        )
    )
    return result.scalar_one_or_none()


async def browse_portfolios(
    db: AsyncSession,
    industry_type:  Optional[IndustryType] = None,
    city:           Optional[str]          = None,
    min_followers:  int                    = 0,
    min_height_cm:  Optional[int]          = None,
    max_height_cm:  Optional[int]          = None,
    skin_tone:      Optional[str]          = None,
    limit:  int = 20,
    offset: int = 0,
) -> List[Portfolio]:
    """
    Brand discovery — browse published portfolios with filters.
    Physical stat filters (height, skin_tone) join to PhysicalStats table.
    """
    query = (
        select(Portfolio)
        .join(InfluencerProfile, Portfolio.influencer_id == InfluencerProfile.id)
        .where(Portfolio.is_public    == True)
        .where(Portfolio.is_published == True)
    )

    if industry_type:
        query = query.where(Portfolio.industry_type == industry_type)
    if city:
        query = query.where(Portfolio.city.ilike(f"%{city}%"))
    if min_followers:
        query = query.where(InfluencerProfile.follower_count >= min_followers)

    # Physical stat filters — join only when needed
    if any([min_height_cm, max_height_cm, skin_tone]):
        query = query.join(PhysicalStats, PhysicalStats.portfolio_id == Portfolio.id)
        if min_height_cm:
            query = query.where(PhysicalStats.height_cm >= min_height_cm)
        if max_height_cm:
            query = query.where(PhysicalStats.height_cm <= max_height_cm)
        if skin_tone:
            query = query.where(PhysicalStats.skin_tone == skin_tone)

    query = (
        query
        .options(
            selectinload(Portfolio.items),
            selectinload(Portfolio.physical_stats),
            selectinload(Portfolio.creator_stats),
            selectinload(Portfolio.custom_fields),
        )
        .order_by(InfluencerProfile.follower_count.desc())
        .limit(limit).offset(offset)
    )
    result = await db.execute(query)
    return result.scalars().all()


# ── Write ─────────────────────────────────────────────────────────────────────

async def create_portfolio(
    db: AsyncSession,
    influencer: InfluencerProfile,
    payload: PortfolioCreate,
) -> Portfolio:
    existing = await get_portfolio_by_influencer(db, influencer.id)
    if existing:
        raise ValueError("Portfolio already exists. Use PATCH to update it.")

    portfolio = Portfolio(
        influencer_id=influencer.id,
        **payload.model_dump(exclude_none=False),
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def update_portfolio(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
    payload: PortfolioUpdate,
) -> Portfolio:
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(portfolio, field, value)
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def publish_portfolio(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
) -> Portfolio:
    """Set is_published=True — makes it visible in brand discovery."""
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")
    portfolio.is_published = True
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


# ── Portfolio Items ───────────────────────────────────────────────────────────

async def add_portfolio_item(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
    payload: PortfolioItemCreate,
) -> PortfolioItem:
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")
    item = PortfolioItem(portfolio_id=portfolio.id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def delete_portfolio_item(
    db: AsyncSession,
    item: PortfolioItem,
    influencer: InfluencerProfile,
    portfolio: Portfolio,
) -> None:
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio item.")
    await db.delete(item)
    await db.flush()


# ── Stats upsert helpers ──────────────────────────────────────────────────────

async def upsert_physical_stats(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
    payload: PhysicalStatsCreate,
) -> PhysicalStats:
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")

    result = await db.execute(
        select(PhysicalStats).where(PhysicalStats.portfolio_id == portfolio.id)
    )
    stats = result.scalar_one_or_none()
    if stats:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(stats, field, value)
    else:
        stats = PhysicalStats(portfolio_id=portfolio.id, **payload.model_dump())
        db.add(stats)
    await db.flush()
    await db.refresh(stats)
    return stats


async def upsert_creator_stats(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
    payload: CreatorStatsCreate,
) -> CreatorStats:
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")

    result = await db.execute(
        select(CreatorStats).where(CreatorStats.portfolio_id == portfolio.id)
    )
    stats = result.scalar_one_or_none()
    if stats:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(stats, field, value)
    else:
        stats = CreatorStats(portfolio_id=portfolio.id, **payload.model_dump())
        db.add(stats)
    await db.flush()
    await db.refresh(stats)
    return stats


async def add_custom_field(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
    payload: CustomFieldCreate,
) -> CustomField:
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")
    field = CustomField(portfolio_id=portfolio.id, **payload.model_dump())
    db.add(field)
    await db.flush()
    await db.refresh(field)
    return field


# ── PDF generation ────────────────────────────────────────────────────────────

async def generate_pdf(
    db: AsyncSession,
    portfolio: Portfolio,
    influencer: InfluencerProfile,
) -> str:
    """
    Generate the portfolio PDF and store the file path on the portfolio row.
    Returns the file path.
    In production: upload to S3, store the public URL instead.
    """
    if portfolio.influencer_id != influencer.id:
        raise PermissionError("You do not own this portfolio.")

    from app.utils.pdf_generator import generate_portfolio_pdf
    file_path = generate_portfolio_pdf(portfolio)

    # Store path (swap for S3 URL in production)
    portfolio.pdf_url          = file_path
    portfolio.pdf_generated_at = datetime.now(timezone.utc)
    db.add(portfolio)
    await db.flush()

    return file_path
