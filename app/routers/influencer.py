import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.routers.links import get_current_user
from app.services.influencer_service import (
    get_profile, create_or_update_profile,
    search_influencers, compute_credibility_score
)

router = APIRouter(prefix="/influencer", tags=["Influencer"])

class ProfileRequest(BaseModel):
    bio: Optional[str] = None
    niche: Optional[str] = None
    instagram_handle: Optional[str] = None
    youtube_channel: Optional[str] = None
    follower_count: Optional[int] = None
    avg_engagement_rate: Optional[float] = None
    city: Optional[str] = None
    profile_image_url: Optional[str] = None
    upi_id: Optional[str] = None

def profile_to_dict(p, user=None):
    return {
        "id": str(p.id),
        "user_id": str(p.user_id),
        "bio": p.bio,
        "niche": p.niche,
        "instagram_handle": p.instagram_handle,
        "youtube_channel": p.youtube_channel,
        "follower_count": p.follower_count,
        "avg_engagement_rate": float(p.avg_engagement_rate or 0),
        "city": p.city,
        "profile_image_url": p.profile_image_url,
        "total_earnings": float(p.total_earnings or 0),
        "total_clicks": p.total_clicks,
        "total_conversions": p.total_conversions,
        "is_verified": p.is_verified,
        "full_name": user.full_name if user else None,
        "email": user.email if user else None,
    }

@router.post("/profile")
async def save_profile(
    payload: ProfileRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await create_or_update_profile(db, current_user, payload.model_dump())
    return profile_to_dict(profile, current_user)

@router.get("/profile/me")
async def get_my_profile(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create one first.")
    return profile_to_dict(profile, current_user)

@router.get("/credibility")
async def my_credibility(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Create your profile first.")
    return compute_credibility_score(profile)

@router.get("/search")
async def search(
    niche: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    min_followers: int = Query(0),
    min_engagement: float = Query(0),
    db: AsyncSession = Depends(get_db),
):
    results = await search_influencers(db, niche=niche, city=city,
                                       min_followers=min_followers,
                                       min_engagement=min_engagement)
    output = []
    for p in results:
        d = profile_to_dict(p)
        d["credibility"] = compute_credibility_score(p)
        output.append(d)
    return output
