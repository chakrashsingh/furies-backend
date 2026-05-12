"""
app/services/affiliate_service.py
───────────────────────────────────
Business logic for affiliate link creation, retrieval, and management.

Authorization rules:
    - CREATE:  influencer — must own the influencer profile
    - READ:    owner can see full stats; public sees nothing (links aren't browsable)
    - TOGGLE:  influencer owner only
    - DELETE:  soft-delete (set is_active=False) — never hard-delete

Click recording and conversion attribution live in click_service.py (Step 6)
and purchase_service.py (Step 7).
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate_link import AffiliateLink
from app.models.influencer import InfluencerProfile
from app.models.product import Product
from app.schemas.affiliate_link import AffiliateLinkCreate
from app.utils.short_code import generate_unique_short_code


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_link_by_id(
    db: AsyncSession, link_id: uuid.UUID
) -> Optional[AffiliateLink]:
    result = await db.execute(
        select(AffiliateLink).where(AffiliateLink.id == link_id)
    )
    return result.scalar_one_or_none()


async def get_link_by_short_code(
    db: AsyncSession, short_code: str
) -> Optional[AffiliateLink]:
    """Used by the redirect endpoint — the hot path."""
    result = await db.execute(
        select(AffiliateLink).where(AffiliateLink.short_code == short_code)
    )
    return result.scalar_one_or_none()


async def get_link_by_alias(
    db: AsyncSession, alias: str
) -> Optional[AffiliateLink]:
    """Lookup by vanity alias (e.g. 'riya-vitc')."""
    result = await db.execute(
        select(AffiliateLink).where(AffiliateLink.custom_alias == alias.lower())
    )
    return result.scalar_one_or_none()


async def list_links_for_influencer(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    active_only: bool = False,
) -> List[AffiliateLink]:
    """Return all links owned by an influencer, newest first."""
    query = select(AffiliateLink).where(AffiliateLink.influencer_id == influencer_id)
    if active_only:
        query = query.where(AffiliateLink.is_active == True)
    query = query.order_by(AffiliateLink.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


# ── Write ─────────────────────────────────────────────────────────────────────

async def create_affiliate_link(
    db: AsyncSession,
    influencer: InfluencerProfile,
    payload: AffiliateLinkCreate,
) -> AffiliateLink:
    """
    Generate a new affiliate link for a product.

    Validations:
        1. Product must exist and be active.
        2. Influencer must not already have a link for this product
           (UniqueConstraint enforces this at DB level too, but we surface
            a clear error here instead of letting Postgres raise IntegrityError).
        3. Custom alias must not already be taken.
    """
    # 1. Check product exists and is active
    product_result = await db.execute(
        select(Product).where(
            Product.id == payload.product_id,
            Product.is_active == True,
        )
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise ValueError("Product not found or is inactive.")

    # 2. Check for duplicate link
    existing = await db.execute(
        select(AffiliateLink).where(
            AffiliateLink.influencer_id == influencer.id,
            AffiliateLink.product_id == payload.product_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(
            "You already have an affiliate link for this product. "
            "Use PATCH to update or reactivate it."
        )

    # 3. Check alias uniqueness
    if payload.custom_alias:
        taken = await get_link_by_alias(db, payload.custom_alias)
        if taken:
            raise ValueError(f"Alias '{payload.custom_alias}' is already taken.")

    # 4. Generate unique short code
    short_code = await generate_unique_short_code(db)

    link = AffiliateLink(
        influencer_id=influencer.id,
        product_id=payload.product_id,
        short_code=short_code,
        custom_alias=payload.custom_alias,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link


async def toggle_link(
    db: AsyncSession,
    link: AffiliateLink,
    influencer: InfluencerProfile,
    is_active: bool,
) -> AffiliateLink:
    """Pause or reactivate a link. Only the owning influencer can do this."""
    if link.influencer_id != influencer.id:
        raise PermissionError("You do not own this affiliate link.")
    link.is_active = is_active
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link
