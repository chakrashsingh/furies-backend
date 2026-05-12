"""
app/services/search_service.py
───────────────────────────────
Internal filtered search — precise brand-brief matching.

This is NOT a fuzzy keyword search.
It's a structured query engine: "find me influencers who match
exactly this brief" — like a casting call with specific requirements.

Uses PostgreSQL's native filtering capabilities through SQLAlchemy.
No external search infrastructure needed.

Two search modes:

1. INFLUENCER SEARCH (for brands)
   Find influencers matching a detailed brief:
   - Niche / industry
   - Follower range
   - Location (city/state)
   - Physical stats (for fashion briefs)
   - Engagement rate threshold
   - Platform (Instagram/YouTube)
   - Credibility score threshold
   - Campaign budget compatibility

2. CAMPAIGN/EVENT SEARCH (for influencers)
   Find open opportunities matching the influencer's profile:
   - Their niche
   - Their follower count
   - Location
   - Paid vs unpaid preference
   - Campaign type
"""

import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.models.event import Event, EventStatus
from app.models.influencer import InfluencerProfile, Niche
from app.models.portfolio import Portfolio, PhysicalStats, IndustryType
from app.models.purchase import Purchase, PurchaseStatus
from app.models.affiliate_link import AffiliateLink
from app.models.user import User


# ─────────────────────────────────────────────────────────────────────────────
# INFLUENCER SEARCH (brand finds talent)
# ─────────────────────────────────────────────────────────────────────────────

async def search_influencers(
    db: AsyncSession,

    # ── Audience filters ──────────────────────────────────────────────────────
    niche:                Optional[str]          = None,
    min_followers:        int                    = 0,
    max_followers:        Optional[int]          = None,
    min_engagement_rate:  Optional[Decimal]      = None,

    # ── Location ──────────────────────────────────────────────────────────────
    city:                 Optional[str]          = None,
    state:                Optional[str]          = None,

    # ── Industry / platform ───────────────────────────────────────────────────
    industry_type:        Optional[IndustryType] = None,
    platform:             Optional[str]          = None,  # "YouTube" | "Instagram" etc.

    # ── Physical stats (fashion briefs) ───────────────────────────────────────
    min_height_cm:        Optional[int]          = None,
    max_height_cm:        Optional[int]          = None,
    skin_tone:            Optional[str]          = None,
    willing_to_travel:    Optional[bool]         = None,

    # ── Credibility ───────────────────────────────────────────────────────────
    min_credibility_score:Optional[int]          = None,

    # ── Has portfolio ─────────────────────────────────────────────────────────
    has_published_portfolio: bool                = False,

    # ── Pagination ────────────────────────────────────────────────────────────
    limit:  int = 20,
    offset: int = 0,
) -> List[dict]:
    """
    Precise influencer search for brand briefs.
    Returns enriched result dicts with influencer + portfolio + stats.
    """
    query = (
        select(InfluencerProfile, User)
        .join(User, InfluencerProfile.user_id == User.id)
    )

    # ── Portfolio join (needed for location + industry + physical filters) ────
    needs_portfolio = any([city, state, industry_type, min_height_cm,
                           max_height_cm, skin_tone, willing_to_travel,
                           has_published_portfolio])
    if needs_portfolio:
        if has_published_portfolio:
            query = query.join(
                Portfolio,
                and_(Portfolio.influencer_id == InfluencerProfile.id,
                     Portfolio.is_published == True)
            )
        else:
            query = query.outerjoin(
                Portfolio, Portfolio.influencer_id == InfluencerProfile.id
            )
        if city:
            query = query.where(Portfolio.city.ilike(f"%{city}%"))
        if state:
            query = query.where(Portfolio.state.ilike(f"%{state}%"))
        if industry_type:
            query = query.where(Portfolio.industry_type == industry_type)

    # ── Physical stat filters ─────────────────────────────────────────────────
    needs_physical = any([min_height_cm, max_height_cm, skin_tone, willing_to_travel])
    if needs_physical:
        query = query.join(
            PhysicalStats, PhysicalStats.portfolio_id == Portfolio.id
        )
        if min_height_cm:
            query = query.where(PhysicalStats.height_cm >= min_height_cm)
        if max_height_cm:
            query = query.where(PhysicalStats.height_cm <= max_height_cm)
        if skin_tone:
            query = query.where(PhysicalStats.skin_tone == skin_tone)
        if willing_to_travel is not None:
            query = query.where(PhysicalStats.willing_to_travel == willing_to_travel)

    # ── Influencer profile filters ────────────────────────────────────────────
    if niche:
        query = query.where(InfluencerProfile.niche == niche)
    if min_followers:
        query = query.where(InfluencerProfile.follower_count >= min_followers)
    if max_followers:
        query = query.where(InfluencerProfile.follower_count <= max_followers)
    if min_engagement_rate:
        query = query.where(InfluencerProfile.avg_engagement_rate >= min_engagement_rate)

    # ── Order: most followers first ───────────────────────────────────────────
    query = (
        query
        .where(InfluencerProfile.follower_count > 0)
        .order_by(InfluencerProfile.follower_count.desc())
        .limit(limit).offset(offset)
        .distinct()
    )

    result = await db.execute(query)
    rows = result.all()

    # ── Enrich with live conversion stats ────────────────────────────────────
    enriched = []
    for inf, user in rows:
        # Credibility score filter (computed, not stored — done post-query)
        score = _compute_credibility_score(inf)
        if min_credibility_score and score < min_credibility_score:
            continue

        enriched.append({
            "influencer_id":      str(inf.id),
            "full_name":          user.full_name,
            "niche":              inf.niche.value,
            "follower_count":     inf.follower_count,
            "avg_engagement_rate":float(inf.avg_engagement_rate),
            "total_clicks":       inf.total_clicks,
            "total_conversions":  inf.total_conversions,
            "total_earnings":     str(inf.total_earnings),
            "credibility_score":  score,
            "is_verified":        inf.is_verified,
        })

    return enriched


def _compute_credibility_score(inf: InfluencerProfile) -> int:
    """
    Compute credibility score inline — used to filter search results.
    Full scoring logic lives in credibility_service.py (Feature 3).
    """
    from app.services.credibility_service import compute_score
    return compute_score(inf)


# ─────────────────────────────────────────────────────────────────────────────
# OPPORTUNITY SEARCH (influencer finds campaigns + events)
# ─────────────────────────────────────────────────────────────────────────────

async def search_opportunities(
    db: AsyncSession,
    # Influencer's own profile to auto-match
    my_niche:          Optional[str]  = None,
    my_followers:      int            = 0,
    my_city:           Optional[str]  = None,
    # Manual overrides
    keyword:           Optional[str]  = None,   # searches title + description
    campaign_type:     Optional[str]  = None,   # paid | unpaid
    opportunity_type:  Optional[str]  = None,   # campaign | event | both
    min_budget:        Optional[Decimal] = None,
    city:              Optional[str]  = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Find open campaigns + events that match an influencer's profile.
    Returns {"campaigns": [...], "events": [...]} grouped by type.
    """
    city_filter = city or my_city

    # ── Campaign search ───────────────────────────────────────────────────────
    campaigns = []
    if opportunity_type in (None, "campaign", "both"):
        c_query = select(Campaign).where(Campaign.status == CampaignStatus.OPEN)

        if my_followers:
            c_query = c_query.where(Campaign.min_followers <= my_followers)
        if my_niche:
            c_query = c_query.where(
                or_(
                    Campaign.target_niches.ilike(f"%{my_niche}%"),
                    Campaign.target_niches.is_(None),
                )
            )
        if campaign_type:
            c_query = c_query.where(Campaign.campaign_type == campaign_type)
        if keyword:
            c_query = c_query.where(
                or_(
                    Campaign.title.ilike(f"%{keyword}%"),
                    Campaign.description.ilike(f"%{keyword}%"),
                )
            )
        if min_budget:
            c_query = c_query.where(Campaign.budget_amount >= min_budget)

        c_query = c_query.order_by(Campaign.created_at.desc()).limit(limit).offset(offset)
        c_result = await db.execute(c_query)
        for c in c_result.scalars().all():
            campaigns.append({
                "id":           str(c.id),
                "type":         "campaign",
                "title":        c.title,
                "campaign_type":c.campaign_type.value,
                "budget_amount":str(c.budget_amount) if c.budget_amount else None,
                "target_niches":c.target_niches,
                "min_followers":c.min_followers,
                "deadline":     c.application_deadline.isoformat() if c.application_deadline else None,
                "created_at":   c.created_at.isoformat(),
                "match_reason": _campaign_match_reason(c, my_niche, my_followers),
            })

    # ── Event search ──────────────────────────────────────────────────────────
    events = []
    if opportunity_type in (None, "event", "both"):
        e_query = select(Event).where(Event.status == EventStatus.OPEN)

        if my_followers:
            e_query = e_query.where(Event.min_followers <= my_followers)
        if city_filter:
            e_query = e_query.where(
                or_(
                    Event.location_city.ilike(f"%{city_filter}%"),
                    Event.is_virtual == True,
                )
            )
        if keyword:
            e_query = e_query.where(
                or_(
                    Event.title.ilike(f"%{keyword}%"),
                    Event.description.ilike(f"%{keyword}%"),
                )
            )
        if campaign_type:  # reuse for paid/unpaid
            e_query = e_query.where(Event.collab_type == campaign_type)
        if min_budget:
            e_query = e_query.where(Event.budget_max >= min_budget)

        e_query = e_query.order_by(Event.event_date.asc().nullslast()).limit(limit).offset(offset)
        e_result = await db.execute(e_query)
        for e in e_result.scalars().all():
            events.append({
                "id":             str(e.id),
                "type":           "event",
                "title":          e.title,
                "event_category": e.event_category.value,
                "collab_type":    e.collab_type.value,
                "budget_min":     str(e.budget_min) if e.budget_min else None,
                "budget_max":     str(e.budget_max) if e.budget_max else None,
                "city":           e.location_city,
                "event_date":     e.event_date.isoformat() if e.event_date else None,
                "is_virtual":     e.is_virtual,
                "match_reason":   _event_match_reason(e, my_followers, city_filter),
            })

    return {
        "campaigns":  campaigns,
        "events":     events,
        "total":      len(campaigns) + len(events),
        "filters_applied": {
            "niche": my_niche, "followers": my_followers,
            "city": city_filter, "keyword": keyword,
        }
    }


def _campaign_match_reason(campaign, niche: Optional[str], followers: int) -> str:
    """Human-readable explanation of why this campaign matched."""
    reasons = []
    if niche and campaign.target_niches and niche in campaign.target_niches:
        reasons.append(f"matches your niche ({niche})")
    if followers and campaign.min_followers <= followers:
        reasons.append(f"you meet the follower requirement ({campaign.min_followers:,}+)")
    if campaign.budget_amount:
        reasons.append(f"paid ₹{campaign.budget_amount:,}")
    return " · ".join(reasons) if reasons else "Open to all influencers"


def _event_match_reason(event, followers: int, city: Optional[str]) -> str:
    reasons = []
    if followers and event.min_followers <= followers:
        reasons.append(f"you qualify ({event.min_followers:,}+ followers)")
    if city and event.location_city and city.lower() in event.location_city.lower():
        reasons.append(f"in your city ({event.location_city})")
    if event.is_virtual:
        reasons.append("virtual event — open to all locations")
    return " · ".join(reasons) if reasons else "Open event"
