"""
app/routers/product.py
───────────────────────
Product CRUD endpoints.

Prefix: /api/v1/products

Permission matrix:
    GET  /           — public (anyone can browse)
    GET  /{id}       — public
    POST /           — brand only
    PATCH/{id}       — brand owner only
    DELETE /{id}     — brand owner only (soft-delete)
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_brand
from app.models.product import ProductType
from app.models.user import User
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.brand_service import get_brand_by_user_id
from app.services.product_service import (
    create_product, delete_product, get_product_by_id,
    list_products, update_product,
)

router = APIRouter(prefix="/products", tags=["Products"])


# ── GET /products/ ────────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=List[ProductResponse],
    summary="Browse product catalogue (public)",
)
async def browse_products(
    brand_id:     Optional[uuid.UUID]   = Query(None, description="Filter by brand"),
    product_type: Optional[ProductType] = Query(None, description="physical | digital | service"),
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await list_products(db, brand_id=brand_id, product_type=product_type,
                               limit=limit, offset=offset)


# ── GET /products/{product_id} ────────────────────────────────────────────────
@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product details (public)",
)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await get_product_by_id(db, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


# ── POST /products/ ───────────────────────────────────────────────────────────
@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product (brand only)",
)
async def create_new_product(
    payload: ProductCreate,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create a brand profile first via POST /brands/profile",
        )
    return await create_product(db, brand, payload)


# ── PATCH /products/{product_id} ──────────────────────────────────────────────
@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update a product (brand owner only)",
)
async def update_existing_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    product = await get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brand profile missing.")

    try:
        return await update_product(db, product, brand, payload)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ── DELETE /products/{product_id} ─────────────────────────────────────────────
@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a product (brand owner only)",
)
async def soft_delete_product(
    product_id: uuid.UUID,
    current_user: User = Depends(require_brand),
    db: AsyncSession = Depends(get_db),
):
    product = await get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    brand = await get_brand_by_user_id(db, current_user.id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brand profile missing.")

    try:
        await delete_product(db, product, brand)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
