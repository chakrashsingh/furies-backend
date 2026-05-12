"""
app/routers/affiliate.py
─────────────────────────
Affiliate link management endpoints.

Prefix: /api/v1/affiliate

Endpoints:
    POST   /affiliate/links              — create a link (influencer only)
    GET    /affiliate/links              — list own links with stats
    GET    /affiliate/links/{link_id}    — get single link detail
    PATCH  /affiliate/links/{link_id}    — toggle active/paused
    DELETE /affiliate/links/{link_id}    — soft-delete

Redirect endpoint (no auth, public hot-path):
    GET    /go/{code_or_alias}           — redirect + record click (Step 6)
    (registered separately in main.py at root level for clean short URLs)
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_influencer
from app.models.user import User
from app.schemas.affiliate_link import (
    AffiliateLinkCreate,
    AffiliateLinkResponse,
    AffiliateLinkToggle,
)
from app.services.affiliate_service import (
    create_affiliate_link,
    get_link_by_id,
    list_links_for_influencer,
    toggle_link,
)
from app.services.influencer_service import get_profile_by_user_id

router = APIRouter(prefix="/affiliate", tags=["Affiliate Links"])


def _build_redirect_url(request: Request, short_code: str) -> str:
    """Construct the public redirect URL from the current request's base URL."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/go/{short_code}"


# ── POST /affiliate/links ─────────────────────────────────────────────────────
@router.post(
    "/links",
    response_model=AffiliateLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new affiliate link for a product (influencer only)",
)
async def create_link(
    payload: AffiliateLinkCreate,
    request: Request,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a unique short link tied to the influencer + product.
    Optional `custom_alias` for a vanity URL (e.g. 'riya-vitc').

    **Request body example:**
    ```json
    {
      "product_id": "<uuid>",
      "custom_alias": "riya-vitc-serum"
    }
    ```
    """
    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your influencer profile first via POST /influencers/profile",
        )
    try:
        link = await create_affiliate_link(db, influencer, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    response = AffiliateLinkResponse.model_validate(link)
    response.redirect_url = _build_redirect_url(request, link.custom_alias or link.short_code)
    return response


# ── GET /affiliate/links ──────────────────────────────────────────────────────
@router.get(
    "/links",
    response_model=List[AffiliateLinkResponse],
    summary="List all affiliate links with performance stats (influencer only)",
)
async def list_my_links(
    request: Request,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Influencer profile not found.")

    links = await list_links_for_influencer(db, influencer.id)
    result = []
    for link in links:
        r = AffiliateLinkResponse.model_validate(link)
        r.redirect_url = _build_redirect_url(request, link.custom_alias or link.short_code)
        result.append(r)
    return result


# ── GET /affiliate/links/{link_id} ────────────────────────────────────────────
@router.get(
    "/links/{link_id}",
    response_model=AffiliateLinkResponse,
    summary="Get a single affiliate link by ID (influencer owner only)",
)
async def get_link(
    link_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer or link.influencer_id != influencer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    response = AffiliateLinkResponse.model_validate(link)
    response.redirect_url = _build_redirect_url(request, link.custom_alias or link.short_code)
    return response


# ── PATCH /affiliate/links/{link_id} ─────────────────────────────────────────
@router.patch(
    "/links/{link_id}",
    response_model=AffiliateLinkResponse,
    summary="Pause or reactivate an affiliate link",
)
async def toggle_link_status(
    link_id: uuid.UUID,
    payload: AffiliateLinkToggle,
    request: Request,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    try:
        link = await toggle_link(db, link, influencer, payload.is_active)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    response = AffiliateLinkResponse.model_validate(link)
    response.redirect_url = _build_redirect_url(request, link.custom_alias or link.short_code)
    return response


# ── DELETE /affiliate/links/{link_id} ────────────────────────────────────────
@router.delete(
    "/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an affiliate link (influencer owner only)",
)
async def delete_link(
    link_id: uuid.UUID,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    try:
        await toggle_link(db, link, influencer, is_active=False)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
