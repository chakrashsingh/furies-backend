"""
app/routers/analytics.py
─────────────────────────
Analytics dashboard API endpoints.

Prefix: /api/v1/analytics

Endpoints:
    GET /analytics/influencer/dashboard       — full influencer dashboard
    GET /analytics/influencer/earnings        — earnings summary + breakdown
    GET /analytics/influencer/links/{id}      — single link earnings chart

    GET /analytics/brand/dashboard            — full brand dashboard
    GET /analytics/brand/products             — product performance table
    GET /analytics/brand/campaigns            — campaign application funnel

    GET /analytics/admin/summary              — platform-wide KPIs
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_brand, require_influencer
from app.models.purchase import Purchase, PurchaseStatus
from app.models.affiliate_link import AffiliateLink
from app.models.user import User
from app.schemas.analytics import (
    AdminSummary, BrandDashboard, DatePoint, InfluencerDashboard,
)
from app.services.analytics_service import (
    get_admin_summary, get_brand_dashboard,
    get_influencer_dashboard, get_link_earnings_series,
)
from app.services.brand_service import get_brand_by_user_id
from app.services.influencer_service import get_profile_by_user_id
from app.services.affiliate_service import get_link_by_id

router = APIRouter(prefix="/analytics", tags=["Analytics Dashboard"])


# ─────────────────────────────────────────────────────────────────────────────
# INFLUENCER ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/influencer/dashboard",
    response_model=InfluencerDashboard,
    summary="Full influencer analytics dashboard",
)
async def influencer_dashboard(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    Returns the complete influencer analytics dashboard including:
    - All-time totals (clicks, conversions, earnings)
    - 30-day window metrics
    - Top 5 links by earnings
    - 5 most recent links
    - Application pipeline (campaigns + events)
    - 30-day time-series charts for earnings, clicks, conversions
    - 10 most recent attributed purchases
    """
    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(
            status_code=404,
            detail="Influencer profile not found. Create one via POST /influencers/profile",
        )
    return await get_influencer_dashboard(db, influencer, current_user)


@router.get(
    "/influencer/links/{link_id}/earnings",
    response_model=List[DatePoint],
    summary="Daily earnings chart for a single affiliate link",
)
async def link_earnings_chart(
    link_id: uuid.UUID,
    days: int = Query(default=30, ge=7, le=90,
                      description="Number of days to look back (7–90)"),
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    Returns a daily earnings time-series for the specified affiliate link.
    Useful for rendering sparkline charts on individual link cards.
    """
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer or link.influencer_id != influencer.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    return await get_link_earnings_series(db, link_id, days=days)


@router.get(
    "/influencer/earnings/summary",
    summary="Quick earnings summary (all-time + 30d + 7d)",
)
async def influencer_earnings_summary(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    Lightweight endpoint for a top-bar earnings widget.
    No charts — just the key numbers.
    """
    from datetime import timedelta, timezone, datetime
    from decimal import Decimal

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer profile not found.")

    since_7d  = datetime.now(timezone.utc) - timedelta(days=7)
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    async def earned_since(since):
        from sqlalchemy import func, select
        r = await db.execute(
            select(func.coalesce(func.sum(Purchase.commission_amount), 0))
            .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
            .where(AffiliateLink.influencer_id == influencer.id)
            .where(Purchase.purchased_at >= since)
            .where(Purchase.status == PurchaseStatus.CONFIRMED)
        )
        return Decimal(str(r.scalar() or 0))

    return {
        "influencer_id":   str(influencer.id),
        "total_earnings":  str(influencer.total_earnings),
        "earnings_30d":    str(await earned_since(since_30d)),
        "earnings_7d":     str(await earned_since(since_7d)),
        "total_clicks":    influencer.total_clicks,
        "total_conversions": influencer.total_conversions,
        "active_links":    (await db.execute(
            select(func.count(AffiliateLink.id)).where(
                AffiliateLink.influencer_id == influencer.id,
                AffiliateLink.is_active == True,
            )
        )).scalar() or 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# BRAND ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/brand/dashboard",
    response_model=BrandDashboard,
    summary="Full brand analytics dashboard",
)
async def brand_dashboard(
    current_user: User = Depends(require_brand),
    db: AsyncSession   = Depends(get_db),
):
    """
    Returns the complete brand analytics dashboard including:
    - All-time revenue + commission paid
    - 30-day window revenue + purchase count
    - Campaign overview (last 10 campaigns + application counts)
    - Top 5 products by revenue
    - Top 5 influencers by conversions driven
    - 30-day daily revenue time-series
    """
    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Brand profile not found. Create one via POST /brands/profile",
        )
    return await get_brand_dashboard(db, brand)


@router.get(
    "/brand/top-influencers",
    summary="Top influencers driving sales for this brand (quick view)",
)
async def brand_top_influencers(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_brand),
    db: AsyncSession   = Depends(get_db),
):
    """
    Returns the top N influencers ranked by revenue driven
    for this brand's products. Useful for outreach / partnership decisions.
    """
    from sqlalchemy import func
    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found.")

    from app.models.product import Product
    from app.models.influencer import InfluencerProfile

    result = await db.execute(
        select(
            AffiliateLink.influencer_id,
            func.count(Purchase.id).label("conversions"),
            func.coalesce(func.sum(Purchase.purchase_amount), 0).label("revenue"),
            func.coalesce(func.sum(Purchase.commission_amount), 0).label("commission"),
        )
        .join(Purchase, Purchase.affiliate_link_id == AffiliateLink.id)
        .join(Product,  AffiliateLink.product_id == Product.id)
        .where(Product.brand_id == brand.id)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .group_by(AffiliateLink.influencer_id)
        .order_by(func.count(Purchase.id).desc())
        .limit(limit)
    )

    rows = result.all()
    output = []
    for row in rows:
        inf_r = await db.execute(
            select(InfluencerProfile, User)
            .join(User, InfluencerProfile.user_id == User.id)
            .where(InfluencerProfile.id == row.influencer_id)
        )
        inf_row = inf_r.one_or_none()
        if inf_row:
            inf, usr = inf_row
            output.append({
                "influencer_id":   str(inf.id),
                "full_name":       usr.full_name,
                "niche":           inf.niche.value,
                "follower_count":  inf.follower_count,
                "conversions":     row.conversions,
                "revenue_driven":  str(Decimal(str(row.revenue))),
                "commission_paid": str(Decimal(str(row.commission))),
            })
    return output


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/admin/summary",
    response_model=AdminSummary,
    summary="Platform-wide KPI summary (admin view)",
)
async def admin_summary(
    # In production: Depends(require_admin)
    # For MVP: any authenticated user can access (add role guard before launch)
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db),
):
    """
    Platform-wide metrics snapshot:
    - User + content counts
    - All-time clicks, conversions, GMV, commissions paid
    - 30-day activity window

    ⚠️  Lock this behind an ADMIN role before production deployment.
    """
    return await get_admin_summary(db)


# ─────────────────────────────────────────────────────────────────────────────
# Utility import needed inside route function above
# ─────────────────────────────────────────────────────────────────────────────
from decimal import Decimal  # noqa — used inside route functions
