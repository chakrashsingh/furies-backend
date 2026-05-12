"""
app/services/campaign_service.py
──────────────────────────────────
Business logic for Campaign CRUD and lifecycle management.

Authorization:
    CREATE / UPDATE / DELETE  — brand owner only
    LIST / GET                — public (open campaigns) + brand sees own drafts
"""

import uuid
from typing import List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.brand import BrandProfile
from app.schemas.campaign import CampaignCreate, CampaignUpdate


async def get_campaign_by_id(
    db: AsyncSession, campaign_id: uuid.UUID
) -> Optional[Campaign]:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    return result.scalar_one_or_none()


async def list_campaigns(
    db: AsyncSession,
    brand_id:       Optional[uuid.UUID]       = None,
    status:         Optional[CampaignStatus]  = None,
    campaign_type:  Optional[str]             = None,
    niche:          Optional[str]             = None,
    max_min_followers: Optional[int]          = None,   # influencer's follower count
    limit:  int = 20,
    offset: int = 0,
) -> List[Campaign]:
    """
    Public campaign marketplace.
    - Without filters → returns all OPEN campaigns (newest first).
    - brand_id filter → returns that brand's campaigns of any status.
    - niche filter → matches against target_niches (contains check).
    - max_min_followers → show campaigns the influencer is eligible for.
    """
    query = select(Campaign)

    if brand_id:
        query = query.where(Campaign.brand_id == brand_id)
    else:
        # Public view: only show open campaigns
        query = query.where(Campaign.status == CampaignStatus.OPEN)

    if status:
        query = query.where(Campaign.status == status)
    if campaign_type:
        query = query.where(Campaign.campaign_type == campaign_type)
    if niche:
        # Simple LIKE check on comma-separated niche string
        query = query.where(Campaign.target_niches.ilike(f"%{niche}%"))
    if max_min_followers is not None:
        query = query.where(Campaign.min_followers <= max_min_followers)

    query = query.order_by(Campaign.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def create_campaign(
    db: AsyncSession,
    brand: BrandProfile,
    payload: CampaignCreate,
) -> Campaign:
    campaign = Campaign(
        brand_id=brand.id,
        **payload.model_dump(exclude_none=False),
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    db: AsyncSession,
    campaign: Campaign,
    brand: BrandProfile,
    payload: CampaignUpdate,
) -> Campaign:
    if campaign.brand_id != brand.id:
        raise PermissionError("You do not own this campaign.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def delete_campaign(
    db: AsyncSession,
    campaign: Campaign,
    brand: BrandProfile,
) -> None:
    """Soft-delete by setting status=CANCELLED."""
    if campaign.brand_id != brand.id:
        raise PermissionError("You do not own this campaign.")
    campaign.status = CampaignStatus.CANCELLED
    db.add(campaign)
    await db.flush()


async def publish_campaign(
    db: AsyncSession,
    campaign: Campaign,
    brand: BrandProfile,
) -> Campaign:
    """Transition campaign from DRAFT → OPEN."""
    if campaign.brand_id != brand.id:
        raise PermissionError("You do not own this campaign.")
    if campaign.status != CampaignStatus.DRAFT:
        raise ValueError(f"Only DRAFT campaigns can be published. Current: {campaign.status}")
    campaign.status = CampaignStatus.OPEN
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign
