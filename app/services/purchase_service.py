"""
app/services/purchase_service.py
──────────────────────────────────
Mock Purchase + Conversion Attribution + Earnings Calculation.

Core flow (record_purchase):
    1. Validate product exists and is active
    2. If session_token provided → look up originating Click
       → resolve AffiliateLink → influencer
    3. Calculate commission:
           commission_amount = purchase_amount × (commission_pct / 100)
    4. Write Purchase row
    5. Mark Click.converted = True
    6. Increment counters on AffiliateLink and InfluencerProfile:
           affiliate_link.conversion_count  += 1
           affiliate_link.total_earned      += commission_amount
           influencer.total_conversions     += 1
           influencer.total_earnings        += commission_amount
    7. Return Purchase

Step 8 note (earnings):
    The earnings calculation IS steps 5–6 above.
    The separate Step 8 in the roadmap refers to the reporting /
    payout summary endpoints — those are in analytics_service.py (Step 12).
    We're building the calculation here at the point of purchase so the
    data is always consistent and never needs a separate recalculation job.
"""

import secrets
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate_link import AffiliateLink
from app.models.click import Click
from app.models.influencer import InfluencerProfile
from app.models.product import Product
from app.models.purchase import Purchase, PurchaseStatus
from app.schemas.purchase import MockPurchaseRequest
from app.services.click_service import get_click_by_session_token, mark_click_converted


def _calculate_commission(amount: Decimal, pct: Decimal) -> Decimal:
    """
    commission = amount × (pct / 100), rounded to 2 decimal places (HALF_UP).
    Example: ₹999.00 × 15% = ₹149.85
    """
    return (amount * (pct / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _generate_order_id() -> str:
    """
    Mock order ID in the style of Razorpay / Shopify order references.
    Format: ORD-<8 uppercase hex chars>
    """
    return f"ORD-{secrets.token_hex(4).upper()}"


async def record_purchase(
    db: AsyncSession,
    payload: MockPurchaseRequest,
) -> tuple[Purchase, Optional[InfluencerProfile]]:
    """
    Record a mock purchase and handle all attribution + earnings side-effects.

    Returns:
        (Purchase, influencer_profile_or_None)

    If no session_token is supplied, or the token doesn't match any click,
    the purchase is still recorded as "unattributed" — the brand still sees
    the sale, but no influencer earns commission.
    """
    # ── 1. Validate product ───────────────────────────────────────────────────
    product_result = await db.execute(
        select(Product).where(Product.id == payload.product_id, Product.is_active == True)
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise ValueError("Product not found or is inactive.")

    # ── 2. Resolve click → affiliate link → influencer via session_token ──────
    click: Optional[Click]              = None
    affiliate_link: Optional[AffiliateLink] = None
    influencer: Optional[InfluencerProfile] = None

    if payload.session_token:
        click = await get_click_by_session_token(db, payload.session_token)
        if click:
            # Verify the click is for the correct product
            link_result = await db.execute(
                select(AffiliateLink).where(
                    AffiliateLink.id         == click.affiliate_link_id,
                    AffiliateLink.product_id == payload.product_id,
                    AffiliateLink.is_active  == True,
                )
            )
            affiliate_link = link_result.scalar_one_or_none()
            if affiliate_link:
                inf_result = await db.execute(
                    select(InfluencerProfile).where(
                        InfluencerProfile.id == affiliate_link.influencer_id
                    )
                )
                influencer = inf_result.scalar_one_or_none()

    # ── 3. Calculate purchase amount + commission ─────────────────────────────
    unit_price      = product.price
    quantity        = payload.quantity
    purchase_amount = payload.override_amount or (unit_price * quantity)

    commission_pct    = product.commission_pct
    commission_amount = _calculate_commission(purchase_amount, commission_pct) \
                        if affiliate_link else Decimal("0.00")

    # ── 4. Write Purchase row ─────────────────────────────────────────────────
    purchase = Purchase(
        affiliate_link_id=affiliate_link.id if affiliate_link else None,
        click_id=click.id if click else None,
        session_token=payload.session_token,
        product_id=payload.product_id,
        purchase_amount=purchase_amount,
        commission_pct=commission_pct,
        commission_amount=commission_amount,
        currency=product.currency,
        buyer_name=payload.buyer_name,
        buyer_email=str(payload.buyer_email) if payload.buyer_email else None,
        order_id=_generate_order_id(),
        status=PurchaseStatus.CONFIRMED,
    )
    db.add(purchase)
    await db.flush()   # get purchase.id before updating counters

    # ── 5–6. Attribution side-effects (only if linked to an influencer) ───────
    if affiliate_link and influencer:
        # Mark the originating click as converted
        if click:
            await mark_click_converted(db, click)

        # Increment affiliate link counters
        affiliate_link.conversion_count += 1
        affiliate_link.total_earned     += commission_amount
        db.add(affiliate_link)

        # Increment influencer aggregate counters
        influencer.total_conversions += 1
        influencer.total_earnings    += commission_amount
        db.add(influencer)

    await db.flush()
    await db.refresh(purchase)
    return purchase, influencer


async def get_purchase_by_id(
    db: AsyncSession, purchase_id: uuid.UUID
) -> Optional[Purchase]:
    result = await db.execute(select(Purchase).where(Purchase.id == purchase_id))
    return result.scalar_one_or_none()


async def list_purchases_for_link(
    db: AsyncSession,
    affiliate_link_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[Purchase]:
    """All purchases attributed to a specific affiliate link, newest first."""
    result = await db.execute(
        select(Purchase)
        .where(Purchase.affiliate_link_id == affiliate_link_id)
        .order_by(Purchase.purchased_at.desc())
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


async def list_purchases_for_influencer(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[Purchase]:
    """
    All purchases across ALL of an influencer's affiliate links.
    Used for the earnings history view.
    """
    result = await db.execute(
        select(Purchase)
        .join(AffiliateLink, Purchase.affiliate_link_id == AffiliateLink.id)
        .where(AffiliateLink.influencer_id == influencer_id)
        .order_by(Purchase.purchased_at.desc())
        .limit(limit).offset(offset)
    )
    return result.scalars().all()
