import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.brand import BrandProfile
from app.models.campaign import Campaign, Application, CampaignStatus
from app.models.user import User

async def get_brand(db: AsyncSession, user_id: uuid.UUID) -> Optional[BrandProfile]:
    result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == user_id))
    return result.scalar_one_or_none()

async def create_or_update_brand(db: AsyncSession, user: User, data: dict) -> BrandProfile:
    brand = await get_brand(db, user.id)
    if brand:
        for k, v in data.items():
            if v is not None:
                setattr(brand, k, v)
    else:
        brand = BrandProfile(user_id=user.id, **{k:v for k,v in data.items() if v is not None})
        db.add(brand)
    await db.flush()
    await db.refresh(brand)
    return brand

async def create_campaign(db: AsyncSession, brand: BrandProfile, data: dict) -> Campaign:
    campaign = Campaign(brand_id=brand.id, **data)
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign

async def get_open_campaigns(db: AsyncSession, niche: Optional[str] = None, limit: int = 20) -> List[Campaign]:
    query = select(Campaign).where(Campaign.status == CampaignStatus.OPEN)
    if niche:
        query = query.where(Campaign.target_niche == niche)
    query = query.order_by(Campaign.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def apply_to_campaign(db: AsyncSession, campaign_id: uuid.UUID, influencer_id: uuid.UUID, cover_letter: str) -> Application:
    dup = await db.execute(
        select(Application).where(Application.campaign_id == campaign_id, Application.influencer_id == influencer_id)
    )
    if dup.scalar_one_or_none():
        raise ValueError("Already applied to this campaign.")
    app = Application(campaign_id=campaign_id, influencer_id=influencer_id, cover_letter=cover_letter)
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return app

async def get_campaign_applications(db: AsyncSession, campaign_id: uuid.UUID) -> List[Application]:
    result = await db.execute(select(Application).where(Application.campaign_id == campaign_id))
    return result.scalars().all()
