"""
app/routers/credibility.py
───────────────────────────
Credibility Score endpoints.

Prefix: /api/v1/credibility

GET /credibility/me              — influencer checks own score + tips
GET /credibility/{influencer_id} — brand checks any influencer's score
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_influencer
from app.models.user import User
from app.services.credibility_service import get_full_report, compute_score, get_badge
from app.services.influencer_service import get_profile_by_id, get_profile_by_user_id

router = APIRouter(prefix="/credibility", tags=["Credibility Score"])


@router.get(
    "/me",
    summary="Your credibility score with full breakdown and improvement tips",
)
async def my_credibility_score(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    Returns your current credibility score (0–100) with:
    - Score per dimension (engagement, conversions, completeness, etc.)
    - Your badge (Elite / Verified / Rising / New / Unverified)
    - Actionable tips to improve your score

    **Sample response:**
    ```json
    {
      "total_score": 72,
      "badge": "Rising",
      "badge_emoji": "📈",
      "breakdown": {
        "engagement_rate":       {"points": 20, "max": 25, "note": "Good: 4.2%"},
        "follower_tier":         {"points": 12, "max": 15, "note": "Mid-tier: 85,000"},
        "platform_conversions":  {"points": 22, "max": 35, "note": "Good rate: 0.8%"},
        "profile_completeness":  {"points": 12, "max": 15, "note": "8/10 fields"},
        "account_stability":     {"points": 8,  "max": 10, "note": "47 days on platform"}
      },
      "what_would_improve_score": [
        "Drive more purchases via your affiliate links — conversion data is our strongest signal"
      ]
    }
    ```
    """
    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(
            status_code=404,
            detail="Influencer profile not found. Create one via POST /influencers/profile"
        )
    return get_full_report(influencer)


@router.get(
    "/{influencer_id}",
    summary="Check any influencer's credibility score (public — brands use this)",
)
async def check_influencer_credibility(
    influencer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Brands call this before accepting a campaign application or
    hiring an influencer for an event.

    Returns the score + badge + breakdown.
    Does NOT expose private data — only the metrics that drive the score.
    """
    influencer = await get_profile_by_id(db, influencer_id)
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found.")
    return get_full_report(influencer)
