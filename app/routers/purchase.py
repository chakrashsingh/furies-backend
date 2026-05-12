"""
app/routers/purchase.py
────────────────────────
Mock Purchase API + purchase history endpoints.

Prefix: /api/v1/purchases

Endpoints:
    POST /purchases/mock           — simulate a purchase (public, no auth)
    GET  /purchases/{purchase_id}  — get purchase detail
    GET  /purchases/my/history     — influencer's attributed purchase history
    GET  /purchases/link/{link_id} — purchases for a specific affiliate link
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_influencer
from app.models.user import User
from app.schemas.purchase import MockPurchaseRequest, PurchaseListItem, PurchaseResponse
from app.services.influencer_service import get_profile_by_user_id
from app.services.purchase_service import (
    get_purchase_by_id,
    list_purchases_for_influencer,
    list_purchases_for_link,
    record_purchase,
)
from app.services.affiliate_service import get_link_by_id

router = APIRouter(prefix="/purchases", tags=["Purchases & Conversions"])


# ── POST /purchases/mock ──────────────────────────────────────────────────────
@router.post(
    "/mock",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a product purchase (no auth required — public mock endpoint)",
)
async def mock_purchase(
    payload: MockPurchaseRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Simulates a buyer completing a purchase.

    **How to test the full affiliate flow:**
    1. Influencer generates a link → gets `redirect_url` with a short code
    2. Visit `GET /go/<code>` → you get redirected, response headers contain
       `X-Session-Token` (or check the redirect URL's `aff_session` param)
    3. POST here with that `session_token` and the same `product_id`
    4. Commission is calculated and credited to the influencer

    **Without session_token:** purchase is recorded but unattributed.

    **Request body example:**
    ```json
    {
      "product_id": "<uuid>",
      "session_token": "<token-from-redirect>",
      "buyer_name": "Priya Patel",
      "buyer_email": "priya@example.com",
      "quantity": 1
    }
    ```
    """
    try:
        purchase, influencer = await record_purchase(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    response = PurchaseResponse.model_validate(purchase)
    if influencer:
        response.influencer_id = influencer.id
        response.attribution   = "attributed"
    elif payload.session_token:
        response.attribution = "unattributed"   # token given but didn't match
    return response


# ── GET /purchases/{purchase_id} ──────────────────────────────────────────────
@router.get(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    summary="Get purchase detail by ID",
)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    purchase = await get_purchase_by_id(db, purchase_id)
    if not purchase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found.")
    return PurchaseResponse.model_validate(purchase)


# ── GET /purchases/my/history ─────────────────────────────────────────────────
@router.get(
    "/my/history",
    response_model=List[PurchaseListItem],
    summary="Influencer's full attributed purchase + earnings history",
)
async def my_purchase_history(
    limit:  int = 50,
    offset: int = 0,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all purchases across all of the influencer's affiliate links,
    newest first. Each row shows the commission earned per sale.
    """
    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Influencer profile not found.")

    return await list_purchases_for_influencer(db, influencer.id, limit=limit, offset=offset)


# ── GET /purchases/link/{link_id} ─────────────────────────────────────────────
@router.get(
    "/link/{link_id}",
    response_model=List[PurchaseListItem],
    summary="All purchases for a specific affiliate link (influencer owner only)",
)
async def purchases_for_link(
    link_id: uuid.UUID,
    limit:   int = 50,
    offset:  int = 0,
    current_user: User = Depends(require_influencer),
    db: AsyncSession = Depends(get_db),
):
    link = await get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    influencer = await get_profile_by_user_id(db, current_user.id)
    if not influencer or link.influencer_id != influencer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return await list_purchases_for_link(db, link_id, limit=limit, offset=offset)
