import uuid
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.influencer import InfluencerProfile, Niche
from app.models.user import User

async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> Optional[InfluencerProfile]:
    result = await db.execute(select(InfluencerProfile).where(InfluencerProfile.user_id == user_id))
    return result.scalar_one_or_none()

async def get_profile_by_id(db: AsyncSession, profile_id: uuid.UUID) -> Optional[InfluencerProfile]:
    result = await db.execute(select(InfluencerProfile).where(InfluencerProfile.id == profile_id))
    return result.scalar_one_or_none()

async def create_or_update_profile(db: AsyncSession, user: User, data: dict) -> InfluencerProfile:
    profile = await get_profile(db, user.id)
    if profile:
        for k, v in data.items():
            if v is not None:
                setattr(profile, k, v)
    else:
        profile = InfluencerProfile(user_id=user.id, **{k:v for k,v in data.items() if v is not None})
        db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile

async def search_influencers(
    db: AsyncSession,
    niche: Optional[str] = None,
    city: Optional[str] = None,
    min_followers: int = 0,
    min_engagement: float = 0,
    limit: int = 20,
) -> List[InfluencerProfile]:
    query = select(InfluencerProfile).where(InfluencerProfile.follower_count >= min_followers)
    if niche:
        query = query.where(InfluencerProfile.niche == niche)
    if city:
        query = query.where(InfluencerProfile.city.ilike(f"%{city}%"))
    if min_engagement:
        query = query.where(InfluencerProfile.avg_engagement_rate >= min_engagement)
    query = query.order_by(InfluencerProfile.follower_count.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

def compute_credibility_score(profile: InfluencerProfile) -> dict:
    score = 0
    breakdown = {}

    # Engagement rate (25 pts)
    rate = float(profile.avg_engagement_rate or 0)
    if rate >= 6:   eng = 25
    elif rate >= 3: eng = 20
    elif rate >= 1: eng = 13
    elif rate > 0:  eng = 5
    else:           eng = 0
    score += eng
    breakdown["engagement_rate"] = {"points": eng, "max": 25, "value": f"{rate}%"}

    # Follower tier (15 pts)
    f = profile.follower_count or 0
    if f >= 100000:   tier = 15
    elif f >= 10000:  tier = 12
    elif f >= 1000:   tier = 8
    else:             tier = 3
    score += tier
    breakdown["follower_tier"] = {"points": tier, "max": 15, "value": f"{f:,} followers"}

    # Platform conversions (35 pts)
    clicks = profile.total_clicks or 0
    convs  = profile.total_conversions or 0
    if clicks == 0:                      conv = 10
    elif (convs/clicks*100) > 3:         conv = 35
    elif (convs/clicks*100) >= 1:        conv = 28
    elif (convs/clicks*100) >= 0.5:      conv = 22
    else:                                conv = 8
    score += conv
    breakdown["conversions"] = {"points": conv, "max": 35, "value": f"{convs} sales from {clicks} clicks"}

    # Profile completeness (15 pts)
    fields = [profile.bio, profile.niche, profile.instagram_handle or profile.youtube_channel,
              profile.city, profile.profile_image_url]
    comp = min(sum(1 for f in fields if f) * 3, 15)
    score += comp
    breakdown["completeness"] = {"points": comp, "max": 15, "value": f"{sum(1 for f in fields if f)}/5 fields"}

    # Account age (10 pts)
    from datetime import datetime, timezone
    days = (datetime.now(timezone.utc) - profile.created_at).days
    if days > 90:   age = 10
    elif days > 30: age = 8
    elif days > 7:  age = 5
    else:           age = 2
    score += age
    breakdown["account_age"] = {"points": age, "max": 10, "value": f"{days} days on platform"}

    score = min(score, 100)
    if score >= 90:   badge = ("Elite", "🏆")
    elif score >= 75: badge = ("Verified", "✅")
    elif score >= 50: badge = ("Rising", "📈")
    elif score >= 25: badge = ("New", "🌱")
    else:             badge = ("Unverified", "⚠️")

    return {"score": score, "badge": badge[0], "emoji": badge[1], "breakdown": breakdown}
