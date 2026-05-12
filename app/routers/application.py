"""
app/routers/application.py
───────────────────────────
Influencer-facing application endpoints.

Prefix: /api/v1/applications

Influencers use this router to:
    - Apply to a campaign or event
    - View all their applications (unified inbox)
    - Withdraw a pending application
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_influencer
from app.models.application import ApplicationStatus, ApplicationType
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate, ApplicationResponse, ApplicationSummary,
)
from app.services.application_service import (
    apply_to_campaign, apply_to_event,
    get_application_by_id,
    list_applications_for_influencer,
    withdraw_application,
)
from app.services.campaign_service import get_campaign_by_id
from app.services.event_service import get_event_by_id
from app.services.influencer_service import get_profile_by_user_id

router = APIRouter(prefix="/applications", tags=["Applications"])


def _get_influencer_or_404(influencer):
    if not influencer:
        raise HTTPException(
            status_code=400,
            detail="Create your influencer profile first via POST /influencers/profile",
        )
    return influencer


# ── GET /applications/ — influencer's unified application inbox ───────────────
@router.get("/", response_model=List[ApplicationSummary],
            summary="Influencer's all applications (campaigns + events)")
async def my_applications(
    app_status: Optional[ApplicationStatus] = Query(None,
        description="Filter by status: pending | accepted | rejected | withdrawn"),
    app_type:   Optional[ApplicationType]   = Query(None,
        description="Filter by type: campaign | event"),
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    influencer = _get_influencer_or_404(
        await get_profile_by_user_id(db, current_user.id)
    )
    return await list_applications_for_influencer(
        db, influencer.id, status=app_status, app_type=app_type
    )


# ── GET /applications/{application_id} ───────────────────────────────────────
@router.get("/{application_id}", response_model=ApplicationResponse,
            summary="Get application detail (influencer owner only)")
async def get_application(
    application_id: uuid.UUID,
    current_user: User  = Depends(require_influencer),
    db: AsyncSession    = Depends(get_db),
):
    application = await get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer or application.influencer_id != influencer.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return application


# ── POST /applications/campaign/{campaign_id} — apply to campaign ─────────────
@router.post("/campaign/{campaign_id}", response_model=ApplicationResponse, status_code=201,
             summary="Apply to a brand campaign (influencer only)")
async def apply_campaign(
    campaign_id: uuid.UUID,
    payload: ApplicationCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    **Request body example:**
    ```json
    {
      "cover_letter": "I love your brand and reach 85k beauty enthusiasts...",
      "proposed_rate": 15000.00,
      "portfolio_url": "https://drive.google.com/my-media-kit"
    }
    ```
    """
    influencer = _get_influencer_or_404(await get_profile_by_user_id(db, current_user.id))

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    try:
        return await apply_to_campaign(db, influencer, campaign, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── POST /applications/event/{event_id} — apply to event ─────────────────────
@router.post("/event/{event_id}", response_model=ApplicationResponse, status_code=201,
             summary="Apply to an event (influencer only)")
async def apply_event(
    event_id: uuid.UUID,
    payload: ApplicationCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    **Request body example:**
    ```json
    {
      "cover_letter": "I would love to cover your wedding reception...",
      "proposed_rate": 8000.00,
      "portfolio_url": "https://instagram.com/riyaskincare"
    }
    ```
    """
    influencer = _get_influencer_or_404(await get_profile_by_user_id(db, current_user.id))

    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    try:
        return await apply_to_event(db, influencer, event, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── DELETE /applications/{application_id} — withdraw ─────────────────────────
@router.delete("/{application_id}", response_model=ApplicationResponse,
               summary="Withdraw a pending application (influencer only)")
async def withdraw(
    application_id: uuid.UUID,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    application = await get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    influencer = _get_influencer_or_404(await get_profile_by_user_id(db, current_user.id))
    try:
        return await withdraw_application(db, application, influencer)
    except (ValueError, PermissionError) as e:
        code = 403 if isinstance(e, PermissionError) else 400
        raise HTTPException(status_code=code, detail=str(e))
