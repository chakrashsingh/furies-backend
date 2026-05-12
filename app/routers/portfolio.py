"""
app/routers/portfolio.py
─────────────────────────
Portfolio system endpoints.

Prefix: /api/v1/portfolio

Influencer endpoints (authenticated):
    POST   /portfolio/                       — create portfolio
    GET    /portfolio/me                     — own portfolio (full detail)
    PATCH  /portfolio/me                     — update portfolio
    POST   /portfolio/me/publish             — make portfolio visible to brands
    POST   /portfolio/me/items               — add image/video/case study
    DELETE /portfolio/me/items/{item_id}     — remove item
    POST   /portfolio/me/physical-stats      — set/update physical measurements
    POST   /portfolio/me/creator-stats       — set/update creator stats
    POST   /portfolio/me/custom-fields       — add a custom field
    POST   /portfolio/me/generate-pdf        — generate/regenerate PDF
    GET    /portfolio/me/download-pdf        — download the PDF

Brand / Public endpoints (no auth or any auth):
    GET    /portfolio/browse                 — discover published portfolios
    GET    /portfolio/{portfolio_id}         — view a specific portfolio
"""

import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_influencer
from app.models.portfolio import IndustryType
from app.models.user import User
from app.schemas.portfolio import (
    CreatorStatsCreate, CreatorStatsResponse,
    CustomFieldCreate, CustomFieldResponse,
    PhysicalStatsCreate, PhysicalStatsResponse,
    PortfolioCreate, PortfolioItemCreate,
    PortfolioItemResponse, PortfolioPublicResponse,
    PortfolioResponse, PortfolioUpdate,
)
from app.services.influencer_service import get_profile_by_user_id
from app.services.portfolio_service import (
    add_custom_field, add_portfolio_item, browse_portfolios,
    create_portfolio, delete_portfolio_item, generate_pdf,
    get_portfolio_by_id, get_portfolio_by_influencer,
    publish_portfolio, update_portfolio,
    upsert_creator_stats, upsert_physical_stats,
)

router = APIRouter(prefix="/portfolio", tags=["Portfolio (Lookout)"])


def _require_profile(influencer):
    if not influencer:
        raise HTTPException(status_code=400,
            detail="Create your influencer profile first via POST /influencers/profile")
    return influencer


def _require_portfolio(portfolio):
    if not portfolio:
        raise HTTPException(status_code=404,
            detail="Portfolio not found. Create one via POST /portfolio/")
    return portfolio


# ── CREATE ────────────────────────────────────────────────────────────────────
@router.post("/", response_model=PortfolioResponse, status_code=201,
             summary="Create your portfolio (influencer only)")
async def create_my_portfolio(
    payload: PortfolioCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    **Example request:**
    ```json
    {
      "display_name": "Riya Sharma",
      "tagline": "Mumbai-based fashion model & lifestyle creator",
      "bio": "5 years in commercial modelling, 85k Instagram followers...",
      "industry_type": "fashion",
      "city": "Mumbai",
      "state": "Maharashtra",
      "profile_image_url": "https://i.imgur.com/example.jpg",
      "instagram_url": "https://instagram.com/riyasharma"
    }
    ```
    """
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    try:
        return await create_portfolio(db, influencer, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── OWN PORTFOLIO ─────────────────────────────────────────────────────────────
@router.get("/me", response_model=PortfolioResponse,
            summary="View own portfolio (full detail)")
async def get_my_portfolio(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    return _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))


@router.patch("/me", response_model=PortfolioResponse,
              summary="Update portfolio headline info")
async def update_my_portfolio(
    payload: PortfolioUpdate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    try:
        return await update_portfolio(db, portfolio, influencer, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/me/publish", response_model=PortfolioResponse,
             summary="Publish portfolio — makes it visible to brands")
async def publish_my_portfolio(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    return await publish_portfolio(db, portfolio, influencer)


# ── PORTFOLIO ITEMS ───────────────────────────────────────────────────────────
@router.post("/me/items", response_model=PortfolioItemResponse, status_code=201,
             summary="Add an image, video link, or brand collab to portfolio")
async def add_item(
    payload: PortfolioItemCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    **Example — add an Instagram reel link:**
    ```json
    {
      "item_type": "video_link",
      "title": "Vitamin C Serum Review — GlowUp Skincare",
      "description": "Full honest review of GlowUp's Vitamin C range",
      "media_url": "https://www.instagram.com/reel/ABC123/",
      "brand_name": "GlowUp Skincare",
      "results": "2.1M views, 8.4% engagement rate",
      "display_order": 1
    }
    ```

    **Example — add a physical photo:**
    ```json
    {
      "item_type": "image",
      "title": "Vogue India Shoot — August 2024",
      "media_url": "https://i.imgur.com/yourphoto.jpg",
      "brand_name": "Vogue India",
      "display_order": 2
    }
    ```
    """
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    try:
        return await add_portfolio_item(db, portfolio, influencer, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/me/items/{item_id}", status_code=204,
               summary="Remove a portfolio item")
async def remove_item(
    item_id: uuid.UUID,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.portfolio import PortfolioItem
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    item_result = await db.execute(
        select(PortfolioItem).where(PortfolioItem.id == item_id)
    )
    item = item_result.scalar_one_or_none()
    if not item or item.portfolio_id != portfolio.id:
        raise HTTPException(status_code=404, detail="Portfolio item not found.")
    await delete_portfolio_item(db, item, influencer, portfolio)


# ── PHYSICAL STATS ────────────────────────────────────────────────────────────
@router.post("/me/physical-stats", response_model=PhysicalStatsResponse,
             summary="Set/update physical measurements (fashion/modelling)")
async def set_physical_stats(
    payload: PhysicalStatsCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    **Example request:**
    ```json
    {
      "height_cm": 173,
      "weight_kg": 58.5,
      "bust_cm": 86,
      "waist_cm": 62,
      "hips_cm": 90,
      "shoe_size_eu": 38,
      "dress_size": "S",
      "skin_tone": "wheatish",
      "hair_color": "black",
      "eye_color": "brown",
      "years_experience": 4,
      "languages": "Hindi,English,Marathi",
      "willing_to_travel": true
    }
    ```
    """
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    try:
        return await upsert_physical_stats(db, portfolio, influencer, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── CREATOR STATS ─────────────────────────────────────────────────────────────
@router.post("/me/creator-stats", response_model=CreatorStatsResponse,
             summary="Set/update creator/YouTuber statistics")
async def set_creator_stats(
    payload: CreatorStatsCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    **Example request:**
    ```json
    {
      "primary_platform": "YouTube",
      "subscriber_count": 245000,
      "avg_views_per_video": 85000,
      "avg_likes_per_post": 4200,
      "posting_frequency": "2 videos/week",
      "audience_age_range": "18-34",
      "audience_gender_split": "55% Female, 45% Male",
      "top_audience_countries": "India,UAE,Singapore",
      "content_categories": "Beauty,Skincare,Lifestyle",
      "collab_types_offered": "Dedicated video, Integration, Shorts, Community post"
    }
    ```
    """
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    try:
        return await upsert_creator_stats(db, portfolio, influencer, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── CUSTOM FIELDS ─────────────────────────────────────────────────────────────
@router.post("/me/custom-fields", response_model=CustomFieldResponse, status_code=201,
             summary="Add a custom industry-specific field to your portfolio")
async def add_custom(
    payload: CustomFieldCreate,
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    Add any custom field specific to your industry.

    **Examples:**
    - Fitness: `{"field_name": "Certifications", "field_value": "ACE CPT, Nutrition Coach"}`
    - Travel:  `{"field_name": "Countries Visited", "field_value": "42"}`
    - Food:    `{"field_name": "Cuisine Speciality", "field_value": "South Indian, Continental"}`
    - Gaming:  `{"field_name": "Main Games", "field_value": "BGMI, Valorant, GTA V"}`
    """
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    try:
        return await add_custom_field(db, portfolio, influencer, payload)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── PDF GENERATION ────────────────────────────────────────────────────────────
@router.post("/me/generate-pdf", status_code=200,
             summary="Generate / regenerate portfolio PDF")
async def generate_portfolio_pdf(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    """
    Generates a professional PDF of your portfolio and stores it.
    Call this after adding all your items, stats, and custom fields.
    Returns the PDF file path (swap for S3 URL in production).
    """
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))
    try:
        # Reload with all relationships
        portfolio = await get_portfolio_by_influencer(db, influencer.id)
        file_path = await generate_pdf(db, portfolio, influencer)
        return {
            "message": "PDF generated successfully.",
            "pdf_path": file_path,
            "generated_at": portfolio.pdf_generated_at,
            "download_url": f"/api/v1/portfolio/me/download-pdf",
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/me/download-pdf",
            summary="Download your portfolio PDF")
async def download_pdf(
    current_user: User = Depends(require_influencer),
    db: AsyncSession   = Depends(get_db),
):
    influencer = _require_profile(await get_profile_by_user_id(db, current_user.id))
    portfolio  = _require_portfolio(await get_portfolio_by_influencer(db, influencer.id))

    if not portfolio.pdf_url or not os.path.exists(portfolio.pdf_url):
        raise HTTPException(
            status_code=404,
            detail="PDF not generated yet. Call POST /portfolio/me/generate-pdf first."
        )
    return FileResponse(
        path=portfolio.pdf_url,
        media_type="application/pdf",
        filename=f"furies_portfolio_{portfolio.display_name.replace(' ', '_')}.pdf",
    )


# ── PUBLIC / BRAND DISCOVERY ──────────────────────────────────────────────────
@router.get("/browse", response_model=List[PortfolioPublicResponse],
            summary="Browse published portfolios — brand discovery")
async def browse(
    industry_type:  Optional[IndustryType] = Query(None),
    city:           Optional[str]          = Query(None),
    min_followers:  int                    = Query(0, ge=0),
    min_height_cm:  Optional[int]          = Query(None, ge=100, le=250,
        description="Minimum height in cm (fashion/modelling filter)"),
    max_height_cm:  Optional[int]          = Query(None, ge=100, le=250),
    skin_tone:      Optional[str]          = Query(None,
        description="fair | wheatish | medium | olive | dusky | dark"),
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await browse_portfolios(
        db, industry_type=industry_type, city=city,
        min_followers=min_followers,
        min_height_cm=min_height_cm, max_height_cm=max_height_cm,
        skin_tone=skin_tone,
        limit=limit, offset=offset,
    )


@router.get("/{portfolio_id}", response_model=PortfolioPublicResponse,
            summary="View a specific portfolio by ID (public)")
async def get_portfolio(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    portfolio = await get_portfolio_by_id(db, portfolio_id)
    if not portfolio or not portfolio.is_published:
        raise HTTPException(status_code=404, detail="Portfolio not found.")
    return portfolio
