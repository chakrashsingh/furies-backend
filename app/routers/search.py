"""
app/routers/search.py
──────────────────────
Internal filtered search endpoints.

Prefix: /api/v1/search

Two search modes:

1. Brand Brief Matching — GET /search/influencers
   Brands enter exact brief requirements → get matching influencers.
   "I need a fashion model in Mumbai, 160–170cm, wheatish skin, 50k+ followers"

2. Opportunity Matching — GET /search/opportunities
   Influencers find open campaigns + events that match their profile.
   "Show me all paid campaigns in beauty that I'm eligible for"
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.portfolio import IndustryType
from app.models.user import User
from app.services.search_service import search_influencers, search_opportunities

router = APIRouter(prefix="/search", tags=["Search Engine"])


# ── GET /search/influencers — Brand brief matching ────────────────────────────
@router.get(
    "/influencers",
    summary="Brand brief matching — find influencers that fit your exact requirements",
)
async def find_influencers(
    # ── Audience ──────────────────────────────────────────────────────────────
    niche: Optional[str] = Query(
        None,
        description="Content niche: fashion | beauty | tech | food | travel | "
                    "fitness | lifestyle | finance | gaming | education | entertainment"
    ),
    min_followers: int = Query(0, ge=0, description="Minimum follower count"),
    max_followers: Optional[int] = Query(None, ge=0, description="Maximum follower count"),
    min_engagement_rate: Optional[Decimal] = Query(
        None, ge=0, description="Minimum engagement rate % (e.g. 2.5 = 2.5%)"
    ),

    # ── Location ──────────────────────────────────────────────────────────────
    city:  Optional[str] = Query(None, description="City e.g. 'Mumbai'"),
    state: Optional[str] = Query(None, description="State e.g. 'Maharashtra'"),

    # ── Industry / platform ───────────────────────────────────────────────────
    industry_type: Optional[IndustryType] = Query(
        None,
        description="Industry: fashion | modelling | youtube | instagram | "
                    "fitness | food_beverage | travel | beauty | tech | gaming"
    ),

    # ── Physical (fashion briefs) ─────────────────────────────────────────────
    min_height_cm: Optional[int] = Query(
        None, ge=100, le=250,
        description="Minimum height in cm (for fashion/modelling briefs)"
    ),
    max_height_cm: Optional[int] = Query(None, ge=100, le=250),
    skin_tone: Optional[str] = Query(
        None,
        description="fair | wheatish | medium | olive | dusky | dark"
    ),
    willing_to_travel: Optional[bool] = Query(
        None, description="Must be willing to travel"
    ),

    # ── Trust ─────────────────────────────────────────────────────────────────
    min_credibility_score: Optional[int] = Query(
        None, ge=0, le=100,
        description="Minimum credibility score (0–100). "
                    "Recommended: 50+ for paid campaigns, 75+ for high-value deals"
    ),
    has_published_portfolio: bool = Query(
        False, description="Only show influencers with published portfolios"
    ),

    # ── Pagination ────────────────────────────────────────────────────────────
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),

    db: AsyncSession = Depends(get_db),
):
    """
    **Example brief: Fashion brand needs models for a campaign**
    ```
    GET /search/influencers?
      niche=fashion&
      city=Mumbai&
      min_followers=20000&
      min_height_cm=163&
      max_height_cm=175&
      skin_tone=wheatish&
      min_engagement_rate=2.5&
      min_credibility_score=50&
      has_published_portfolio=true
    ```

    **Example brief: Tech brand needs YouTubers**
    ```
    GET /search/influencers?
      niche=tech&
      industry_type=youtube&
      min_followers=50000&
      min_engagement_rate=3.0&
      min_credibility_score=60
    ```

    Each result includes `credibility_score` and `match_badge` so you
    can immediately see how trustworthy each influencer is.
    """
    results = await search_influencers(
        db,
        niche=niche,
        min_followers=min_followers,
        max_followers=max_followers,
        min_engagement_rate=min_engagement_rate,
        city=city,
        state=state,
        industry_type=industry_type,
        min_height_cm=min_height_cm,
        max_height_cm=max_height_cm,
        skin_tone=skin_tone,
        willing_to_travel=willing_to_travel,
        min_credibility_score=min_credibility_score,
        has_published_portfolio=has_published_portfolio,
        limit=limit,
        offset=offset,
    )

    # Attach badge to each result
    from app.services.credibility_service import get_badge
    for r in results:
        badge_name, badge_emoji = get_badge(r["credibility_score"])
        r["credibility_badge"] = f"{badge_emoji} {badge_name}"

    return {
        "results":       results,
        "total_returned":len(results),
        "filters": {
            "niche": niche, "city": city,
            "min_followers": min_followers, "max_followers": max_followers,
            "min_height_cm": min_height_cm, "max_height_cm": max_height_cm,
            "skin_tone": skin_tone, "industry_type": str(industry_type) if industry_type else None,
            "min_credibility_score": min_credibility_score,
        }
    }


# ── GET /search/opportunities — Influencer finds work ─────────────────────────
@router.get(
    "/opportunities",
    summary="Find open campaigns + events matching your profile (influencer)",
)
async def find_opportunities(
    # Auto-matched from your profile — or override manually
    niche:        Optional[str] = Query(None, description="Your niche (auto-filled from profile)"),
    my_followers: int           = Query(0, ge=0, description="Your follower count"),
    my_city:      Optional[str] = Query(None, description="Your city"),

    # Manual filters
    keyword:      Optional[str] = Query(None, description="Search title/description"),
    collab_type:  Optional[str] = Query(None, description="paid | unpaid"),
    show:         Optional[str] = Query(
        None, description="campaign | event | both (default: both)"
    ),
    min_budget:   Optional[Decimal] = Query(None, ge=0),
    city:         Optional[str]     = Query(None, description="Override city filter"),

    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),

    db: AsyncSession = Depends(get_db),
):
    """
    Influencers use this to find open work that matches their profile.

    **Example: Beauty influencer in Mumbai with 85k followers**
    ```
    GET /search/opportunities?
      niche=beauty&
      my_followers=85000&
      my_city=Mumbai&
      collab_type=paid
    ```

    **Example: Search for a specific brand's opportunities**
    ```
    GET /search/opportunities?keyword=GlowUp&show=campaign
    ```

    Returns `campaigns` and `events` grouped separately,
    each with a `match_reason` explaining why it was returned.
    """
    results = await search_opportunities(
        db,
        my_niche=niche,
        my_followers=my_followers,
        my_city=my_city,
        keyword=keyword,
        campaign_type=collab_type,
        opportunity_type=show or "both",
        min_budget=min_budget,
        city=city,
        limit=limit,
        offset=offset,
    )
    return results
