import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.routers.links import get_current_user
from app.services.portfolio_service import (
    get_portfolio, get_portfolio_by_id, save_portfolio,
    add_portfolio_item, delete_portfolio_item,
    save_physical_stats, publish_portfolio,
    browse_portfolios, portfolio_to_dict
)

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

class PortfolioRequest(BaseModel):
    display_name: str
    tagline: Optional[str] = None
    bio: Optional[str] = None
    industry_type: Optional[str] = None
    city: Optional[str] = None
    profile_image_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    twitter_url: Optional[str] = None

class PortfolioItemRequest(BaseModel):
    item_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    media_url: Optional[str] = None
    brand_name: Optional[str] = None
    results: Optional[str] = None
    display_order: int = 0

class PhysicalStatsRequest(BaseModel):
    height_cm: Optional[int] = None
    weight_kg: Optional[str] = None
    bust_cm: Optional[int] = None
    waist_cm: Optional[int] = None
    hips_cm: Optional[int] = None
    shoe_size: Optional[str] = None
    dress_size: Optional[str] = None
    skin_tone: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    languages: Optional[str] = None
    willing_to_travel: bool = True

@router.post("/save")
async def save(
    payload: PortfolioRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await save_portfolio(db, current_user, payload.model_dump())
    return portfolio_to_dict(portfolio)

@router.get("/me")
async def get_my_portfolio(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await get_portfolio(db, current_user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found.")
    return portfolio_to_dict(portfolio)

@router.post("/items/add")
async def add_item(
    payload: PortfolioItemRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await get_portfolio(db, current_user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Create portfolio first.")
    item = await add_portfolio_item(db, portfolio, payload.model_dump())
    return {"id": str(item.id), "title": item.title, "item_type": item.item_type}

@router.delete("/items/{item_id}")
async def remove_item(
    item_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_portfolio_item(db, item_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found.")
    return {"message": "Deleted successfully"}

@router.post("/physical-stats")
async def save_stats(
    payload: PhysicalStatsRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await get_portfolio(db, current_user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Create portfolio first.")
    stats = await save_physical_stats(db, portfolio, payload.model_dump())
    return {"message": "Stats saved!", "height_cm": stats.height_cm}

@router.post("/publish")
async def publish(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await publish_portfolio(db, current_user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Create portfolio first.")
    return {"message": "Portfolio published!", "id": str(portfolio.id)}

@router.get("/browse")
async def browse(
    industry: Optional[str] = None,
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    portfolios = await browse_portfolios(db, industry=industry, city=city)
    return [portfolio_to_dict(p) for p in portfolios]

@router.get("/{portfolio_id}")
async def get_public_portfolio(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    portfolio = await get_portfolio_by_id(db, portfolio_id)
    if not portfolio or not portfolio.is_published:
        raise HTTPException(status_code=404, detail="Portfolio not found.")
    return portfolio_to_dict(portfolio)
