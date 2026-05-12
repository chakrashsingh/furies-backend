"""
app/services/application_service.py
─────────────────────────────────────
Business logic for the Application system.

Key rules:
    1. An influencer can apply to a campaign OR event — not both in one application.
    2. Duplicate applications (same influencer + same campaign/event) are blocked.
    3. Only PENDING applications can be accepted / rejected.
    4. Only PENDING applications can be withdrawn by the influencer.
    5. The decision (accept/reject) is made by:
         - Brand's User account  → for campaign applications
         - Event poster's User   → for event applications
    6. Accepting an application does NOT auto-reject others (brands may
       accept multiple influencers). max_influencers is advisory.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationStatus, ApplicationType
from app.models.campaign import Campaign
from app.models.event import Event
from app.models.influencer import InfluencerProfile
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationDecision


# ── Read helpers ──────────────────────────────────────────────────────────────

async def get_application_by_id(
    db: AsyncSession, application_id: uuid.UUID
) -> Optional[Application]:
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    return result.scalar_one_or_none()


async def list_applications_for_influencer(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    status: Optional[ApplicationStatus] = None,
    app_type: Optional[ApplicationType] = None,
) -> List[Application]:
    """All applications submitted by an influencer (newest first)."""
    query = select(Application).where(Application.influencer_id == influencer_id)
    if status:
        query = query.where(Application.status == status)
    if app_type:
        query = query.where(Application.application_type == app_type)
    query = query.order_by(Application.applied_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def list_applications_for_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    status: Optional[ApplicationStatus] = None,
) -> List[Application]:
    """All influencer applications for a specific campaign."""
    query = select(Application).where(Application.campaign_id == campaign_id)
    if status:
        query = query.where(Application.status == status)
    query = query.order_by(Application.applied_at.asc())
    result = await db.execute(query)
    return result.scalars().all()


async def list_applications_for_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    status: Optional[ApplicationStatus] = None,
) -> List[Application]:
    """All influencer applications for a specific event."""
    query = select(Application).where(Application.event_id == event_id)
    if status:
        query = query.where(Application.status == status)
    query = query.order_by(Application.applied_at.asc())
    result = await db.execute(query)
    return result.scalars().all()


# ── Write: Apply ──────────────────────────────────────────────────────────────

async def apply_to_campaign(
    db: AsyncSession,
    influencer: InfluencerProfile,
    campaign: Campaign,
    payload: ApplicationCreate,
) -> Application:
    """
    Influencer applies to a campaign.
    Validates:
        - Campaign is OPEN
        - No duplicate application
        - Influencer meets min_followers requirement
    """
    from app.models.campaign import CampaignStatus
    if campaign.status != CampaignStatus.OPEN:
        raise ValueError(f"This campaign is not accepting applications (status: {campaign.status}).")

    if influencer.follower_count < campaign.min_followers:
        raise ValueError(
            f"This campaign requires at least {campaign.min_followers:,} followers. "
            f"Your count: {influencer.follower_count:,}."
        )

    # Duplicate check
    dup = await db.execute(
        select(Application).where(
            Application.influencer_id == influencer.id,
            Application.campaign_id   == campaign.id,
        )
    )
    if dup.scalar_one_or_none():
        raise ValueError("You have already applied to this campaign.")

    app = Application(
        influencer_id=influencer.id,
        application_type=ApplicationType.CAMPAIGN,
        campaign_id=campaign.id,
        cover_letter=payload.cover_letter,
        proposed_rate=payload.proposed_rate,
        portfolio_url=payload.portfolio_url,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return app


async def apply_to_event(
    db: AsyncSession,
    influencer: InfluencerProfile,
    event: Event,
    payload: ApplicationCreate,
) -> Application:
    """
    Influencer applies to an event.
    Validates:
        - Event is OPEN
        - No duplicate application
        - Influencer meets min_followers requirement
    """
    from app.models.event import EventStatus
    if event.status != EventStatus.OPEN:
        raise ValueError(f"This event is not accepting applications (status: {event.status}).")

    if influencer.follower_count < event.min_followers:
        raise ValueError(
            f"This event requires at least {event.min_followers:,} followers. "
            f"Your count: {influencer.follower_count:,}."
        )

    dup = await db.execute(
        select(Application).where(
            Application.influencer_id == influencer.id,
            Application.event_id      == event.id,
        )
    )
    if dup.scalar_one_or_none():
        raise ValueError("You have already applied to this event.")

    app = Application(
        influencer_id=influencer.id,
        application_type=ApplicationType.EVENT,
        event_id=event.id,
        cover_letter=payload.cover_letter,
        proposed_rate=payload.proposed_rate,
        portfolio_url=payload.portfolio_url,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return app


# ── Write: Decision ───────────────────────────────────────────────────────────

async def decide_application(
    db: AsyncSession,
    application: Application,
    deciding_user: User,
    payload: ApplicationDecision,
) -> Application:
    """
    Brand or event host accepts / rejects an application.

    Authorization:
        - Campaign applications: the deciding user must own the brand
          that posted the campaign.
        - Event applications: the deciding user must have posted the event.

    Only PENDING → ACCEPTED or PENDING → REJECTED transitions are allowed.
    """
    # Guard: only pending apps can be decided
    if application.status != ApplicationStatus.PENDING:
        raise ValueError(
            f"Cannot change decision on an application with status '{application.status}'. "
            "Only PENDING applications can be accepted or rejected."
        )

    # Guard: decision must be accept or reject (not pending/withdrawn)
    if payload.status not in (ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED):
        raise ValueError("Decision must be 'accepted' or 'rejected'.")

    # Authorization check
    if application.application_type == ApplicationType.CAMPAIGN:
        if not application.campaign:
            raise ValueError("Campaign not found.")
        # Verify deciding_user owns the brand that created this campaign
        from app.services.brand_service import get_brand_by_user_id
        brand = await get_brand_by_user_id(db, deciding_user.id)
        if not brand or brand.id != application.campaign.brand_id:
            raise PermissionError("Only the brand that created this campaign can decide applications.")

    elif application.application_type == ApplicationType.EVENT:
        if not application.event:
            raise ValueError("Event not found.")
        if application.event.posted_by_user_id != deciding_user.id:
            raise PermissionError("Only the user who posted this event can decide applications.")

    # Apply decision
    application.status           = payload.status
    application.decision_note    = payload.decision_note
    application.decided_at       = datetime.now(timezone.utc)
    application.decided_by_user_id = deciding_user.id

    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application


async def withdraw_application(
    db: AsyncSession,
    application: Application,
    influencer: InfluencerProfile,
) -> Application:
    """Influencer withdraws their own PENDING application."""
    if application.influencer_id != influencer.id:
        raise PermissionError("You did not submit this application.")
    if application.status != ApplicationStatus.PENDING:
        raise ValueError("Only PENDING applications can be withdrawn.")
    application.status = ApplicationStatus.WITHDRAWN
    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application
