"""
app/routers/tracking.py
────────────────────────
Public redirect + click tracking endpoint.
Also exposes click history for influencer analytics.

Route registered at ROOT level (not /api/v1) so links stay clean:
    GET /go/{code_or_alias}    → redirect to product URL

Additional authenticated routes:
    GET /api/v1/clicks/{link_id}/stats    → aggregated stats for a link
    GET /api/v1/clicks/{link_id}/history  → raw click rows (influencer only)
"""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_influencer
from app.models.click import Click
from app.models.user import User
from app.schemas.click import ClickDetail, ClickStats
from app.services.affiliate_service import (
    get_link_by_alias, get_link_by_short_code, get_link_by_id
)
from app.services.click_service import record_click
from app.services.influencer_service import get_profile_by_user_id

# ── Redirect router (root-level, no prefix) ───────────────────────────────────
redirect_router = APIRouter(tags=["Affiliate Redirect"])

# ── Analytics router (mounted under /api/v1) ──────────────────────────────────
clicks_router = APIRouter(prefix="/clicks", tags=["Click Analytics"])


def _extract_ip(request: Request) -> Optional[str]:
    """
    Extract real client IP respecting X-Forwarded-For (set by reverse proxies).
    Falls back to direct connection IP.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


# ── GET /go/{code_or_alias} ───────────────────────────────────────────────────
@redirect_router.get(
    "/go/{code_or_alias}",
    summary="Affiliate redirect — records click and redirects to product",
    response_description="302 redirect to the product URL",
    status_code=status.HTTP_302_FOUND,
    include_in_schema=True,
)
async def affiliate_redirect(
    code_or_alias: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    The hot path. Flow:
    1. Resolve code or vanity alias → AffiliateLink
    2. Guard: link must be active
    3. Record click (dedup check, session token issued)
    4. 302 redirect to product URL with ?aff_session=<token> appended

    The `aff_session` query param is picked up by the mock purchase
    API (Step 7) to attribute the conversion back to this influencer.
    """
    # 1. Resolve — try short_code first, then alias
    link = await get_link_by_short_code(db, code_or_alias)
    if not link:
        link = await get_link_by_alias(db, code_or_alias)
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Affiliate link '{code_or_alias}' not found.",
        )

    # 2. Guard: inactive links serve a 410 Gone
    if not link.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This affiliate link has been deactivated.",
        )

    # 3. Record click
    ip       = _extract_ip(request)
    ua       = request.headers.get("User-Agent")
    referrer = request.headers.get("Referer")
    click, session_token = await record_click(db, link, ip, ua, referrer)

    # 4. Build destination URL
    destination = link.product.product_url if link.product.product_url else "/"
    # Append session token so the purchase API can trace back to this click
    sep = "&" if "?" in destination else "?"
    redirect_to = f"{destination}{sep}aff_session={session_token}"

    return RedirectResponse(url=redirect_to, status_code=status.HTTP_302_FOUND)


# ── GET /api/v1/clicks/{link_id}/stats ───────────────────────────────────────
@clicks_router.get(
    "/{link_id}/stats",
    response_model=ClickStats,
    summary="Aggregated click stats for a specific affiliate link (influencer only)",
)
async def get_link_stats(
    link_id: uuid.UUID,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns total clicks, unique clicks, conversions, and conversion rate
    for a single affiliate link. Only accessible by the owning influencer.
    """
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer or link.influencer_id != influencer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Aggregate directly from Click table (source of truth)
    total_result = await db.execute(
        select(func.count(Click.id)).where(Click.affiliate_link_id == link_id)
    )
    unique_result = await db.execute(
        select(func.count(Click.id)).where(
            Click.affiliate_link_id == link_id,
            Click.is_unique == True,
        )
    )
    conv_result = await db.execute(
        select(func.count(Click.id)).where(
            Click.affiliate_link_id == link_id,
            Click.converted == True,
        )
    )

    total   = total_result.scalar() or 0
    unique  = unique_result.scalar() or 0
    convs   = conv_result.scalar() or 0
    rate    = round((convs / unique * 100), 2) if unique > 0 else 0.0

    return ClickStats(
        affiliate_link_id=link_id,
        total_clicks=total,
        unique_clicks=unique,
        conversions=convs,
        conversion_rate=rate,
    )


# ── GET /api/v1/clicks/{link_id}/history ──────────────────────────────────────
@clicks_router.get(
    "/{link_id}/history",
    response_model=List[ClickDetail],
    summary="Raw click history for a link (influencer only, newest first)",
)
async def get_click_history(
    link_id: uuid.UUID,
    limit:  int = 50,
    offset: int = 0,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer or link.influencer_id != influencer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    result = await db.execute(
        select(Click)
        .where(Click.affiliate_link_id == link_id)
        .order_by(Click.clicked_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
