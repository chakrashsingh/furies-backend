"""
app/services/click_service.py
──────────────────────────────
Click recording — the hot path of the entire affiliate system.

Flow when someone visits /go/<code>:
    1. Resolve code → AffiliateLink (check is_active)
    2. Check dedup:  same IP + same link within 24h → is_unique=False
    3. Write Click row (session_token issued here)
    4. Increment AffiliateLink.click_count (unique clicks only)
    5. Increment InfluencerProfile.total_clicks (unique clicks only)
    6. Return (destination_url, session_token) for the redirect response

session_token design:
    - Generated with secrets.token_urlsafe(32) → 43 URL-safe chars
    - Returned to the client as a query param on the redirect URL:
        https://product.com/landing?aff_session=<token>
    - Step 7 (MockPurchase) receives this token to tie the purchase
      back to the exact click row and influencer.
    - In production this would live in a secure HttpOnly cookie.
      For this MVP we use a query param (simpler, no cookie setup needed).

Dedup window: 24 hours per (ip_address, affiliate_link_id).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate_link import AffiliateLink
from app.models.click import Click
from app.models.influencer import InfluencerProfile


_SESSION_TOKEN_BYTES = 32       # → 43 char URL-safe string
_DEDUP_WINDOW_HOURS  = 24


def _new_session_token() -> str:
    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)


async def _is_duplicate_click(
    db: AsyncSession,
    affiliate_link_id,
    ip_address: Optional[str],
) -> bool:
    """
    Return True if this IP already clicked this link in the last 24 hours.
    If ip_address is None (e.g. behind a proxy with no forwarding), treat as unique.
    """
    if not ip_address:
        return False

    window_start = datetime.now(timezone.utc) - timedelta(hours=_DEDUP_WINDOW_HOURS)
    result = await db.execute(
        select(func.count(Click.id)).where(
            Click.affiliate_link_id == affiliate_link_id,
            Click.ip_address       == ip_address,
            Click.clicked_at       >= window_start,
            Click.is_unique        == True,
        )
    )
    return result.scalar() > 0


async def record_click(
    db: AsyncSession,
    affiliate_link: AffiliateLink,
    ip_address: Optional[str],
    user_agent: Optional[str],
    referrer: Optional[str],
) -> Tuple[Click, str]:
    """
    Record a click event. Returns (Click, session_token).

    The session_token is passed downstream to the purchase API so
    Step 7 can link the conversion back to this exact click.
    """
    session_token = _new_session_token()
    is_dup = await _is_duplicate_click(db, affiliate_link.id, ip_address)

    # ── Write Click row ───────────────────────────────────────────────────────
    click = Click(
        affiliate_link_id=affiliate_link.id,
        ip_address=ip_address,
        user_agent=user_agent,
        referrer=referrer,
        session_token=session_token,
        is_unique=not is_dup,
    )
    db.add(click)

    # ── Increment denormalised counters (unique clicks only) ──────────────────
    if not is_dup:
        affiliate_link.click_count += 1

        # Also update the influencer's aggregate total
        influencer_result = await db.execute(
            select(InfluencerProfile).where(
                InfluencerProfile.id == affiliate_link.influencer_id
            )
        )
        influencer = influencer_result.scalar_one_or_none()
        if influencer:
            influencer.total_clicks += 1
            db.add(influencer)

    db.add(affiliate_link)
    await db.flush()
    await db.refresh(click)
    return click, session_token


async def get_click_by_session_token(
    db: AsyncSession, session_token: str
) -> Optional[Click]:
    """Used by Step 7 to find the originating click from a purchase."""
    result = await db.execute(
        select(Click).where(Click.session_token == session_token)
    )
    return result.scalar_one_or_none()


async def mark_click_converted(db: AsyncSession, click: Click) -> Click:
    """Called by purchase_service (Step 7) after a purchase is confirmed."""
    click.converted = True
    db.add(click)
    await db.flush()
    await db.refresh(click)
    return click
