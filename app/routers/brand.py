import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.routers.links import get_current_user
from app.services.brand_service import (
    get_brand, create_or_update_brand, create_campaign,
    get_open_campaigns, apply_to_campaign, get_campaign_applications
)
from app.services.influencer_service import get_profile

router = APIRouter(prefix="/brand", tags=["Brand"])

class BrandRequest(BaseModel):
    company_name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    contact_email: Optional[str] = None

class CampaignRequest(BaseModel):
    title: str
    description: Optional[str] = None
    budget: Optional[float] = None
    commission_pct: Optional[float] = 10
    target_niche: Optional[str] = None
    min_followers: Optional[int] = 0
    is_paid: Optional[bool] = True

class ApplyRequest(BaseModel):
    cover_letter: Optional[str] = None

def campaign_to_dict(c):
    return {
        "id": str(c.id),
        "title": c.title,
        "description": c.description,
        "budget": float(c.budget) if c.budget else None,
        "commission_pct": float(c.commission_pct),
        "target_niche": c.target_niche,
        "min_followers": c.min_followers,
        "status": c.status,
        "is_paid": c.is_paid,
        "created_at": str(c.created_at),
    }

@router.post("/profile")
async def save_brand_profile(
    payload: BrandRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    brand = await create_or_update_brand(db, current_user, payload.model_dump())
    return {"id": str(brand.id), "company_name": brand.company_name,
            "industry": brand.industry, "description": brand.description}

@router.get("/profile/me")
async def get_my_brand(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    brand = await get_brand(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found.")
    return {"id": str(brand.id), "company_name": brand.company_name,
            "industry": brand.industry, "description": brand.description,
            "website": brand.website}

@router.post("/campaigns")
async def post_campaign(
    payload: CampaignRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    brand = await get_brand(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=400, detail="Create brand profile first.")
    campaign = await create_campaign(db, brand, payload.model_dump())
    return campaign_to_dict(campaign)

@router.get("/campaigns")
async def list_campaigns(
    niche: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    campaigns = await get_open_campaigns(db, niche=niche)
    return [campaign_to_dict(c) for c in campaigns]

@router.post("/campaigns/{campaign_id}/apply")
async def apply(
    campaign_id: uuid.UUID,
    payload: ApplyRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="Create influencer profile first.")
    try:
        app = await apply_to_campaign(db, campaign_id, profile.id, payload.cover_letter or "")
        return {"message": "Applied successfully!", "application_id": str(app.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/campaigns/{campaign_id}/applications")
async def campaign_applications(
    campaign_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    apps = await get_campaign_applications(db, campaign_id)
    return [{"id": str(a.id), "influencer_id": str(a.influencer_id),
             "cover_letter": a.cover_letter, "status": a.status,
             "applied_at": str(a.applied_at)} for a in apps]
