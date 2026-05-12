"""
app/routers/campaign.py
────────────────────────
Campaign marketplace endpoints.

Prefix: /api/v1/campaigns

Permission matrix:
    GET  /              — public (open campaigns only)
    GET  /{id}          — public
    GET  /my/campaigns  — brand sees own campaigns (all statuses)
    POST /              — brand only
    POST /{id}/publish  — brand only (draft → open)
    PATCH/{id}          — brand owner only
    DELETE /{id}        — brand owner (soft-cancel)
    GET  /{id}/applications — brand owner only
    POST /{id}/applications/{app_id}/decide — brand owner only
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_brand, require_influencer
from app.models.application import ApplicationStatus
from app.models.user import User
from app.schemas.application import ApplicationDecision, ApplicationResponse, ApplicationSummary
from app.schemas.campaign import CampaignCreate, CampaignResponse, CampaignSummary, CampaignUpdate
from app.services.application_service import (
    decide_application, get_application_by_id,
    list_applications_for_campaign,
)
from app.services.brand_service import get_brand_by_user_id
from app.services.campaign_service import (
    create_campaign, delete_campaign, get_campaign_by_id,
    list_campaigns, publish_campaign, update_campaign,
)

router = APIRouter(prefix="/campaigns", tags=["Campaigns (Marketplace)"])


# ── GET /campaigns/ — public marketplace ─────────────────────────────────────
@router.get("/", response_model=List[CampaignSummary], summary="Browse open campaigns (public)")
async def browse_campaigns(
    campaign_type:   Optional[str] = Query(None, description="paid | unpaid"),
    niche:           Optional[str] = Query(None, description="Filter by niche e.g. 'beauty'"),
    my_followers:    Optional[int] = Query(None, ge=0,
        description="Your follower count — filters to campaigns you're eligible for"),
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await list_campaigns(
        db, campaign_type=campaign_type, niche=niche,
        max_min_followers=my_followers, limit=limit, offset=offset,
    )


# ── GET /campaigns/my/campaigns — brand's own campaigns ──────────────────────
@router.get("/my/campaigns", response_model=List[CampaignSummary],
            summary="Brand's own campaigns (all statuses)")
async def my_campaigns(
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found.")
    return await list_campaigns(db, brand_id=brand.id, limit=100)


# ── GET /campaigns/{campaign_id} ──────────────────────────────────────────────
@router.get("/{campaign_id}", response_model=CampaignResponse, summary="Campaign detail (public)")
async def get_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign


# ── POST /campaigns/ ──────────────────────────────────────────────────────────
@router.post("/", response_model=CampaignResponse, status_code=201,
             summary="Create a campaign (brand only, starts as DRAFT)")
async def create_new_campaign(
    payload: CampaignCreate,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=400, detail="Create a brand profile first.")
    return await create_campaign(db, brand, payload)


# ── POST /campaigns/{campaign_id}/publish ─────────────────────────────────────
@router.post("/{campaign_id}/publish", response_model=CampaignResponse,
             summary="Publish a draft campaign → OPEN (brand only)")
async def publish(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    brand = await get_brand_by_user_id(db, current_user.id)
    try:
        return await publish_campaign(db, campaign, brand)
    except (ValueError, PermissionError) as e:
        code = 403 if isinstance(e, PermissionError) else 400
        raise HTTPException(status_code=code, detail=str(e))


# ── PATCH /campaigns/{campaign_id} ────────────────────────────────────────────
@router.patch("/{campaign_id}", response_model=CampaignResponse,
              summary="Update a campaign (brand owner only)")
async def update(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    brand = await get_brand_by_user_id(db, current_user.id)
    try:
        return await update_campaign(db, campaign, brand, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── DELETE /campaigns/{campaign_id} ───────────────────────────────────────────
@router.delete("/{campaign_id}", status_code=204,
               summary="Cancel a campaign (brand owner only)")
async def cancel(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    brand = await get_brand_by_user_id(db, current_user.id)
    try:
        await delete_campaign(db, campaign, brand)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── GET /campaigns/{campaign_id}/applications ─────────────────────────────────
@router.get("/{campaign_id}/applications", response_model=List[ApplicationSummary],
            summary="View applications for a campaign (brand owner only)")
async def get_campaign_applications(
    campaign_id: uuid.UUID,
    app_status: Optional[ApplicationStatus] = Query(None),
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand or campaign.brand_id != brand.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return await list_applications_for_campaign(db, campaign_id, status=app_status)


# ── POST /campaigns/{campaign_id}/applications/{app_id}/decide ───────────────
@router.post("/{campaign_id}/applications/{app_id}/decide",
             response_model=ApplicationResponse,
             summary="Accept or reject an application (brand only)")
async def decide_campaign_application(
    campaign_id: uuid.UUID,
    app_id: uuid.UUID,
    payload: ApplicationDecision,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    application = await get_application_by_id(db, app_id)
    if not application or application.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Application not found.")
    try:
        return await decide_application(db, application, current_user, payload)
    except (ValueError, PermissionError) as e:
        code = 403 if isinstance(e, PermissionError) else 400
        raise HTTPException(status_code=code, detail=str(e))
