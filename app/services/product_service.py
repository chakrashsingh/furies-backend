"""
app/services/product_service.py
─────────────────────────────────
Business logic for Product CRUD.

Authorization rules:
    - CREATE / UPDATE / DELETE: brand owner only
    - READ (list, get): public
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductType
from app.models.brand import BrandProfile
from app.schemas.product import ProductCreate, ProductUpdate


async def get_product_by_id(
    db: AsyncSession, product_id: uuid.UUID
) -> Optional[Product]:
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def list_products(
    db: AsyncSession,
    brand_id: Optional[uuid.UUID] = None,
    product_type: Optional[ProductType] = None,
    active_only: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> List[Product]:
    """
    Public product catalogue.
    - Filter by brand, product type, or active status.
    - Ordered newest first.
    """
    query = select(Product)
    if brand_id:
        query = query.where(Product.brand_id == brand_id)
    if product_type:
        query = query.where(Product.product_type == product_type)
    if active_only:
        query = query.where(Product.is_active == True)
    query = query.order_by(Product.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def create_product(
    db: AsyncSession,
    brand: BrandProfile,
    payload: ProductCreate,
) -> Product:
    product = Product(
        brand_id=brand.id,
        **payload.model_dump(),
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def update_product(
    db: AsyncSession,
    product: Product,
    brand: BrandProfile,
    payload: ProductUpdate,
) -> Product:
    """
    Only the owning brand can update.
    Raises PermissionError if brand_id doesn't match.
    """
    if product.brand_id != brand.id:
        raise PermissionError("You do not own this product.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def delete_product(
    db: AsyncSession,
    product: Product,
    brand: BrandProfile,
) -> None:
    """
    Soft-delete only — sets is_active=False.
    Hard delete is dangerous: existing affiliate links reference this product.
    """
    if product.brand_id != brand.id:
        raise PermissionError("You do not own this product.")
    product.is_active = False
    db.add(product)
    await db.flush()
