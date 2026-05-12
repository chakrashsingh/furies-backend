import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.link_service import (
    create_link, get_link_by_code, get_my_links,
    record_click, get_earnings_summary,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(prefix="/links", tags=["Affiliate Links"])
redirect_router = APIRouter(tags=["Redirect"])
bearer = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token.")
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

class GenerateLinkRequest(BaseModel):
    url: str
    product_title: Optional[str] = None

@router.post("/generate", status_code=201)
async def generate_link(
    payload: GenerateLinkRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Please enter a valid URL starting with http")
    link = await create_link(db, current_user, payload.url, payload.product_title)
    base = str(request.base_url).rstrip("/")
    return {
        "id": str(link.id),
        "short_code": link.short_code,
        "furies_link": f"{base}/go/{link.short_code}",
        "original_url": link.original_url,
        "platform": link.platform,
        "product_title": link.product_title,
        "commission_rate": float(link.commission_rate),
        "click_count": link.click_count,
        "total_earned": float(link.total_earned),
    }

@router.get("/my-links")
async def my_links(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    links = await get_my_links(db, current_user.id)
    base  = str(request.base_url).rstrip("/")
    return [
        {
            "id": str(l.id),
            "short_code": l.short_code,
            "furies_link": f"{base}/go/{l.short_code}",
            "original_url": l.original_url,
            "platform": l.platform,
            "product_title": l.product_title,
            "commission_rate": float(l.commission_rate),
            "click_count": l.click_count,
            "total_earned": float(l.total_earned),
        }
        for l in links
    ]

@router.get("/earnings")
async def earnings(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_earnings_summary(db, current_user.id)

@redirect_router.get("/go/{code}")
async def redirect(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    link = await get_link_by_code(db, code)
    if not link or not link.is_active:
        raise HTTPException(status_code=404, detail="Link not found.")
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    ua = request.headers.get("User-Agent")
    await record_click(db, link, ip, ua)
    return RedirectResponse(url=link.cuelinks_url or link.original_url, status_code=302)
