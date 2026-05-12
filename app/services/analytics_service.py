"""
app/services/analytics_service.py
───────────────────────────────────
All analytics aggregation logic lives here.

Design principles:
    1. READ-ONLY  — this service never writes. Zero side-effects.
    2. SINGLE DB ROUND-TRIP per chart wherever possible — window functions
       and subqueries beat N+1 loops every time.
    3. FALLBACK TO DENORMALISED COUNTERS for all-time totals:
       influencer.total_earnings, affiliate_link.click_count etc.
       These were maintained atomically by write services (Steps 6, 7).
       We only hit the raw Click / Purchase tables for period queries
       and time-series where the counters don't have enough granularity.
    4. ZEROS NOT NULLS — every numeric field defaults to 0 / 0.00 so
       the frontend never crashes on None checks.
"""

import uuid
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate_link import AffiliateLink
from app.models.application import Application, ApplicationStatus, ApplicationType
from app.models.campaign import Campaign
from app.models.click import Click
from app.models.event import Event
from app.models.influencer import InfluencerProfile
from app.models.brand import BrandProfile
from app.models.product import Product
from app.models.purchase import Purchase, PurchaseStatus
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AdminSummary, ApplicationPipeline, BrandDashboard,
    CampaignStat, DatePoint, InfluencerDashboard,
    LinkPerformance, ProductPerformance, TopInfluencer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: date window
# ─────────────────────────────────────────────────────────────────────────────

def _window_start(days: int = 30) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _zero_decimal() -> Decimal:
    return Decimal("0.00")


# ─────────────────────────────────────────────────────────────────────────────
# Influencer Analytics
# ─────────────────────────────────────────────────────────────────────────────

async def _get_link_performance(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    limit: int = 5,
    order_by_earnings: bool = True,
) -> List[LinkPerformance]:
    """
    Fetch affiliate link performance rows for an influencer.
    Joins AffiliateLink → Product for names.
    Uses denormalised counters (O(1) per link).
    """
    query = (
        select(AffiliateLink, Product.name.label("product_name"))
        .join(Product, AffiliateLink.product_id == Product.id)
        .where(AffiliateLink.influencer_id == influencer_id)
    )
    if order_by_earnings:
        query = query.order_by(AffiliateLink.total_earned.desc())
    else:
        query = query.order_by(AffiliateLink.created_at.desc())
    query = query.limit(limit)

    result = await db.execute(query)
    rows = result.all()

    links = []
    for row in rows:
        link: AffiliateLink = row[0]
        product_name: str   = row[1]
        unique_clicks = link.click_count     # denormalised = unique clicks
        convs         = link.conversion_count
        rate = round(convs / unique_clicks * 100, 2) if unique_clicks > 0 else 0.0
        links.append(LinkPerformance(
            link_id=link.id,
            short_code=link.short_code,
            custom_alias=link.custom_alias,
            product_name=product_name,
            product_id=link.product_id,
            click_count=link.click_count,
            conversion_count=link.conversion_count,
            total_earned=link.total_earned,
            conversion_rate=rate,
            is_active=link.is_active,
        ))
    return links


async def _get_application_pipeline(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    app_type: ApplicationType,
) -> ApplicationPipeline:
    """Count applications by status for one influencer + one type."""
    result = await db.execute(
        select(Application.status, func.count(Application.id).label("cnt"))
        .where(
            Application.influencer_id    == influencer_id,
            Application.application_type == app_type,
        )
        .group_by(Application.status)
    )
    counts = {row.status: row.cnt for row in result}
    pending   = counts.get(ApplicationStatus.PENDING,   0)
    accepted  = counts.get(ApplicationStatus.ACCEPTED,  0)
    rejected  = counts.get(ApplicationStatus.REJECTED,  0)
    withdrawn = counts.get(ApplicationStatus.WITHDRAWN, 0)
    return ApplicationPipeline(
        pending=pending, accepted=accepted,
        rejected=rejected, withdrawn=withdrawn,
        total=pending + accepted + rejected + withdrawn,
    )


async def _time_series(
    db: AsyncSession,
    model,
    amount_col,
    filter_col,
    filter_val: uuid.UUID,
    days: int = 30,
) -> List[DatePoint]:
    """
    Generic daily time-series aggregator.
    Groups rows by calendar date and sums amount_col.
    Returns a point for every day in the window, filling zeros for missing days.
    """
    since = _window_start(days)
    result = await db.execute(
        select(
            cast(filter_col, Date).label("day"),
            func.coalesce(func.sum(amount_col), 0).label("total"),
        )
        .where(model.affiliate_link_id == filter_val)
        .where(filter_col >= since)
        .group_by("day")
        .order_by("day")
    )
    raw = {row.day: Decimal(str(row.total)) for row in result}

    # Build complete date range with zero-fill
    series = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        series.append(DatePoint(date=d.isoformat(), value=raw.get(d, _zero_decimal())))
    return series


async def _influencer_earnings_series(
    db: AsyncSession, influencer_id: uuid.UUID, days: int = 30
) -> List[DatePoint]:
    """Daily earnings for an influencer across all their links."""
    since = _window_start(days)
    result = await db.execute(
        select(
            cast(Purchase.purchased_at, Date).label("day"),
            func.coalesce(func.sum(Purchase.commission_amount), 0).label("total"),
        )
        .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer_id)
        .where(Purchase.purchased_at >= since)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .group_by("day")
        .order_by("day")
    )
    raw = {row.day: Decimal(str(row.total)) for row in result}
    series = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        series.append(DatePoint(date=d.isoformat(), value=raw.get(d, _zero_decimal())))
    return series


async def _influencer_clicks_series(
    db: AsyncSession, influencer_id: uuid.UUID, days: int = 30
) -> List[DatePoint]:
    """Daily unique click counts for an influencer."""
    since = _window_start(days)
    result = await db.execute(
        select(
            cast(Click.clicked_at, Date).label("day"),
            func.count(Click.id).label("cnt"),
        )
        .join(AffiliateLink, Click.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer_id)
        .where(Click.clicked_at >= since)
        .where(Click.is_unique == True)
        .group_by("day")
        .order_by("day")
    )
    raw = {row.day: Decimal(row.cnt) for row in result}
    series = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        series.append(DatePoint(date=d.isoformat(), value=raw.get(d, _zero_decimal())))
    return series


async def _influencer_conversions_series(
    db: AsyncSession, influencer_id: uuid.UUID, days: int = 30
) -> List[DatePoint]:
    """Daily conversion counts for an influencer."""
    since = _window_start(days)
    result = await db.execute(
        select(
            cast(Purchase.purchased_at, Date).label("day"),
            func.count(Purchase.id).label("cnt"),
        )
        .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer_id)
        .where(Purchase.purchased_at >= since)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .group_by("day")
        .order_by("day")
    )
    raw = {row.day: Decimal(row.cnt) for row in result}
    series = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        series.append(DatePoint(date=d.isoformat(), value=raw.get(d, _zero_decimal())))
    return series


async def get_influencer_dashboard(
    db: AsyncSession,
    influencer: InfluencerProfile,
    user: User,
) -> InfluencerDashboard:
    """
    Assembles the full influencer dashboard in one async function.
    Fires ~10 DB queries total — acceptable for a dashboard endpoint
    that isn't called on every page render.
    """
    since_30d = _window_start(30)

    # ── 30-day window totals ──────────────────────────────────────────────────
    clicks_30d_result = await db.execute(
        select(func.count(Click.id))
        .join(AffiliateLink, Click.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer.id)
        .where(Click.clicked_at >= since_30d)
        .where(Click.is_unique == True)
    )
    clicks_30d = clicks_30d_result.scalar() or 0

    earnings_30d_result = await db.execute(
        select(func.coalesce(func.sum(Purchase.commission_amount), 0))
        .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer.id)
        .where(Purchase.purchased_at >= since_30d)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
    )
    earnings_30d = Decimal(str(earnings_30d_result.scalar() or 0))

    conversions_30d_result = await db.execute(
        select(func.count(Purchase.id))
        .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer.id)
        .where(Purchase.purchased_at >= since_30d)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
    )
    conversions_30d = conversions_30d_result.scalar() or 0

    # ── Link performance ──────────────────────────────────────────────────────
    top_links    = await _get_link_performance(db, influencer.id, limit=5, order_by_earnings=True)
    recent_links = await _get_link_performance(db, influencer.id, limit=5, order_by_earnings=False)

    # ── Application pipelines ─────────────────────────────────────────────────
    campaign_pipe = await _get_application_pipeline(db, influencer.id, ApplicationType.CAMPAIGN)
    event_pipe    = await _get_application_pipeline(db, influencer.id, ApplicationType.EVENT)

    # ── Time series ───────────────────────────────────────────────────────────
    earnings_chart    = await _influencer_earnings_series(db, influencer.id)
    clicks_chart      = await _influencer_clicks_series(db, influencer.id)
    conversions_chart = await _influencer_conversions_series(db, influencer.id)

    # ── Recent attributed purchases ───────────────────────────────────────────
    recent_purchases_result = await db.execute(
        select(Purchase)
        .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer.id)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .order_by(Purchase.purchased_at.desc())
        .limit(10)
    )
    recent_purchases = [
        {
            "id":               str(p.id),
            "product_id":       str(p.product_id),
            "purchase_amount":  str(p.purchase_amount),
            "commission_amount":str(p.commission_amount),
            "currency":         p.currency,
            "order_id":         p.order_id,
            "purchased_at":     p.purchased_at.isoformat(),
        }
        for p in recent_purchases_result.scalars().all()
    ]

    # ── Overall conversion rate ───────────────────────────────────────────────
    rate = (
        round(influencer.total_conversions / influencer.total_clicks * 100, 2)
        if influencer.total_clicks > 0 else 0.0
    )

    return InfluencerDashboard(
        influencer_id=influencer.id,
        full_name=user.full_name,
        niche=influencer.niche.value,
        follower_count=influencer.follower_count,
        total_clicks=influencer.total_clicks,
        total_conversions=influencer.total_conversions,
        total_earnings=influencer.total_earnings,
        overall_conversion_rate=rate,
        clicks_30d=clicks_30d,
        conversions_30d=conversions_30d,
        earnings_30d=earnings_30d,
        top_links=top_links,
        recent_links=recent_links,
        campaign_applications=campaign_pipe,
        event_applications=event_pipe,
        earnings_chart=earnings_chart,
        clicks_chart=clicks_chart,
        conversions_chart=conversions_chart,
        recent_purchases=recent_purchases,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Brand Analytics
# ─────────────────────────────────────────────────────────────────────────────

async def get_brand_dashboard(
    db: AsyncSession,
    brand: BrandProfile,
) -> BrandDashboard:
    """Full brand analytics dashboard."""
    since_30d = _window_start(30)

    # ── All-time totals ───────────────────────────────────────────────────────
    total_products_r = await db.execute(
        select(func.count(Product.id)).where(Product.brand_id == brand.id)
    )
    total_products = total_products_r.scalar() or 0

    total_campaigns_r = await db.execute(
        select(func.count(Campaign.id)).where(Campaign.brand_id == brand.id)
    )
    total_campaigns = total_campaigns_r.scalar() or 0

    # Purchases for this brand's products via affiliate links
    revenue_r = await db.execute(
        select(
            func.count(Purchase.id).label("cnt"),
            func.coalesce(func.sum(Purchase.purchase_amount), 0).label("revenue"),
            func.coalesce(func.sum(Purchase.commission_amount), 0).label("commission"),
        )
        .join(Product, Purchase.product_id == Product.id)
        .where(Product.brand_id == brand.id)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
    )
    rev_row          = revenue_r.one()
    total_purchases  = rev_row.cnt       or 0
    total_revenue    = Decimal(str(rev_row.revenue    or 0))
    total_commission = Decimal(str(rev_row.commission or 0))

    # ── 30-day window ─────────────────────────────────────────────────────────
    rev_30d_r = await db.execute(
        select(
            func.count(Purchase.id).label("cnt"),
            func.coalesce(func.sum(Purchase.purchase_amount), 0).label("rev"),
        )
        .join(Product, Purchase.product_id == Product.id)
        .where(Product.brand_id == brand.id)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .where(Purchase.purchased_at >= since_30d)
    )
    row_30d      = rev_30d_r.one()
    purchases_30d = row_30d.cnt or 0
    revenue_30d   = Decimal(str(row_30d.rev or 0))

    # ── Campaign stats ────────────────────────────────────────────────────────
    campaigns_r = await db.execute(
        select(Campaign).where(Campaign.brand_id == brand.id)
        .order_by(Campaign.created_at.desc()).limit(10)
    )
    campaign_rows = campaigns_r.scalars().all()
    campaign_stats = []
    for c in campaign_rows:
        apps_r = await db.execute(
            select(func.count(Application.id)).where(Application.campaign_id == c.id)
        )
        accepted_r = await db.execute(
            select(func.count(Application.id)).where(
                Application.campaign_id == c.id,
                Application.status == ApplicationStatus.ACCEPTED,
            )
        )
        campaign_stats.append(CampaignStat(
            campaign_id=c.id,
            title=c.title,
            status=c.status,
            total_applications=apps_r.scalar() or 0,
            accepted=accepted_r.scalar() or 0,
            budget_amount=c.budget_amount,
            created_at=c.created_at,
        ))

    # ── Top products ──────────────────────────────────────────────────────────
    top_products_r = await db.execute(
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.count(Purchase.id).label("total_purchases"),
            func.coalesce(func.sum(Purchase.purchase_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(Purchase.commission_amount), 0).label("total_commission"),
        )
        .join(Purchase, Purchase.product_id == Product.id, isouter=True)
        .where(Product.brand_id == brand.id)
        .group_by(Product.id, Product.name)
        .order_by(func.coalesce(func.sum(Purchase.purchase_amount), 0).desc())
        .limit(5)
    )
    top_products = []
    for row in top_products_r:
        # Count affiliate links per product
        links_r = await db.execute(
            select(func.count(AffiliateLink.id))
            .where(AffiliateLink.product_id == row.product_id)
        )
        top_products.append(ProductPerformance(
            product_id=row.product_id,
            product_name=row.product_name,
            total_purchases=row.total_purchases,
            total_revenue=Decimal(str(row.total_revenue)),
            total_commission=Decimal(str(row.total_commission)),
            affiliate_links=links_r.scalar() or 0,
        ))

    # ── Top influencers (by conversions for this brand's products) ────────────
    top_inf_r = await db.execute(
        select(
            AffiliateLink.influencer_id,
            func.count(Purchase.id).label("total_conversions"),
            func.coalesce(func.sum(Purchase.purchase_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(Purchase.commission_amount), 0).label("total_commission"),
        )
        .join(Purchase, Purchase.affiliate_link_id == AffiliateLink.id)
        .join(Product, AffiliateLink.product_id == Product.id)
        .where(Product.brand_id == brand.id)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .group_by(AffiliateLink.influencer_id)
        .order_by(func.count(Purchase.id).desc())
        .limit(5)
    )
    top_influencers = []
    for row in top_inf_r:
        inf_r = await db.execute(
            select(InfluencerProfile, User)
            .join(User, InfluencerProfile.user_id == User.id)
            .where(InfluencerProfile.id == row.influencer_id)
        )
        inf_row = inf_r.one_or_none()
        if inf_row:
            inf, usr = inf_row
            top_influencers.append(TopInfluencer(
                influencer_id=inf.id,
                full_name=usr.full_name,
                niche=inf.niche.value,
                total_conversions=row.total_conversions,
                total_revenue=Decimal(str(row.total_revenue)),
                total_commission=Decimal(str(row.total_commission)),
            ))

    # ── Revenue time-series ───────────────────────────────────────────────────
    rev_series_r = await db.execute(
        select(
            cast(Purchase.purchased_at, Date).label("day"),
            func.coalesce(func.sum(Purchase.purchase_amount), 0).label("total"),
        )
        .join(Product, Purchase.product_id == Product.id)
        .where(Product.brand_id == brand.id)
        .where(Purchase.purchased_at >= since_30d)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .group_by("day")
        .order_by("day")
    )
    raw_rev = {row.day: Decimal(str(row.total)) for row in rev_series_r}
    revenue_chart = []
    for i in range(30):
        d = (datetime.now(timezone.utc) - timedelta(days=29 - i)).date()
        revenue_chart.append(DatePoint(date=d.isoformat(), value=raw_rev.get(d, _zero_decimal())))

    return BrandDashboard(
        brand_id=brand.id,
        company_name=brand.company_name,
        total_products=total_products,
        total_campaigns=total_campaigns,
        total_purchases=total_purchases,
        total_revenue=total_revenue,
        total_commission=total_commission,
        revenue_30d=revenue_30d,
        purchases_30d=purchases_30d,
        campaigns=campaign_stats,
        top_products=top_products,
        top_influencers=top_influencers,
        revenue_chart=revenue_chart,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Admin / Platform-wide Analytics
# ─────────────────────────────────────────────────────────────────────────────

async def get_admin_summary(db: AsyncSession) -> AdminSummary:
    """Platform-wide KPI summary — all tables, one pass each."""
    since_30d = _window_start(30)

    async def count(model, *filters):
        q = select(func.count(model.id))
        for f in filters:
            q = q.where(f)
        r = await db.execute(q)
        return r.scalar() or 0

    async def total(model, col, *filters):
        q = select(func.coalesce(func.sum(col), 0))
        for f in filters:
            q = q.where(f)
        r = await db.execute(q)
        return Decimal(str(r.scalar() or 0))

    return AdminSummary(
        # ── User counts
        total_users=       await count(User),
        total_influencers= await count(InfluencerProfile),
        total_brands=      await count(BrandProfile),
        # ── Content
        total_products=        await count(Product),
        total_affiliate_links= await count(AffiliateLink),
        total_campaigns=       await count(Campaign),
        total_events=          await count(Event),
        total_applications=    await count(Application),
        # ── Transactions
        total_clicks=      await count(Click),
        total_conversions= await count(Click, Click.converted == True),
        total_purchases=   await count(Purchase, Purchase.status == PurchaseStatus.CONFIRMED),
        gross_merchandise_value= await total(
            Purchase, Purchase.purchase_amount,
            Purchase.status == PurchaseStatus.CONFIRMED
        ),
        total_commissions_paid= await total(
            Purchase, Purchase.commission_amount,
            Purchase.status == PurchaseStatus.CONFIRMED
        ),
        # ── 30-day activity
        new_users_30d=  await count(User, User.created_at >= since_30d),
        purchases_30d=  await count(
            Purchase,
            Purchase.status == PurchaseStatus.CONFIRMED,
            Purchase.purchased_at >= since_30d,
        ),
        gmv_30d= await total(
            Purchase, Purchase.purchase_amount,
            Purchase.status == PurchaseStatus.CONFIRMED,
            Purchase.purchased_at >= since_30d,
        ),
        generated_at=datetime.now(timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-link analytics (used by tracking router — already partially built)
# ─────────────────────────────────────────────────────────────────────────────

async def get_link_earnings_series(
    db: AsyncSession,
    affiliate_link_id: uuid.UUID,
    days: int = 30,
) -> List[DatePoint]:
    """Daily earnings for a single affiliate link."""
    since = _window_start(days)
    result = await db.execute(
        select(
            cast(Purchase.purchased_at, Date).label("day"),
            func.coalesce(func.sum(Purchase.commission_amount), 0).label("total"),
        )
        .where(Purchase.affiliate_link_id == affiliate_link_id)
        .where(Purchase.purchased_at >= since)
        .where(Purchase.status == PurchaseStatus.CONFIRMED)
        .group_by("day")
        .order_by("day")
    )
    raw = {row.day: Decimal(str(row.total)) for row in result}
    series = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        series.append(DatePoint(date=d.isoformat(), value=raw.get(d, _zero_decimal())))
    return series
