import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.link import AffiliateLink, Click
from app.models.user import User

ALPHABET = string.ascii_letters + string.digits

PLATFORM_MAP = {
    "amazon.in": "Amazon", "amazon.com": "Amazon",
    "flipkart.com": "Flipkart", "myntra.com": "Myntra",
    "nykaa.com": "Nykaa", "ajio.com": "Ajio",
    "meesho.com": "Meesho", "snapdeal.com": "Snapdeal",
    "bewakoof.com": "Bewakoof", "firstcry.com": "FirstCry",
}

COMMISSION_RATES = {
    "Amazon": 4.0, "Flipkart": 8.0, "Myntra": 8.0,
    "Nykaa": 6.0, "Ajio": 8.0, "Meesho": 12.0,
    "Snapdeal": 6.0, "Bewakoof": 10.0, "FirstCry": 5.0,
}

def detect_platform(url: str) -> str:
    url_lower = url.lower()
    for domain, name in PLATFORM_MAP.items():
        if domain in url_lower:
            return name
    return "Other"

def get_commission_rate(platform: str) -> float:
    return COMMISSION_RATES.get(platform, 5.0)

async def generate_short_code(db: AsyncSession) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(ALPHABET) for _ in range(8))
        exists = await db.execute(
            select(AffiliateLink).where(AffiliateLink.short_code == code)
        )
        if not exists.scalar_one_or_none():
            return code
    return secrets.token_urlsafe(8)[:8]

async def create_link(
    db: AsyncSession, user: User,
    original_url: str, product_title: Optional[str] = None
) -> AffiliateLink:
    platform   = detect_platform(original_url)
    commission = get_commission_rate(platform)
    code       = await generate_short_code(db)
    link = AffiliateLink(
        user_id=user.id,
        original_url=original_url,
        cuelinks_url=original_url,
        short_code=code,
        product_title=product_title or f"Product on {platform}",
        platform=platform,
        commission_rate=commission,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link

async def get_link_by_code(db: AsyncSession, code: str) -> Optional[AffiliateLink]:
    result = await db.execute(
        select(AffiliateLink).where(AffiliateLink.short_code == code)
    )
    return result.scalar_one_or_none()

async def get_my_links(db: AsyncSession, user_id: uuid.UUID) -> List[AffiliateLink]:
    result = await db.execute(
        select(AffiliateLink)
        .where(AffiliateLink.user_id == user_id)
        .order_by(AffiliateLink.created_at.desc())
    )
    return result.scalars().all()

async def record_click(
    db: AsyncSession, link: AffiliateLink,
    ip: Optional[str], user_agent: Optional[str]
) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    dup = await db.execute(
        select(func.count(Click.id)).where(
            Click.link_id == link.id,
            Click.ip_address == ip,
            Click.clicked_at >= since,
        )
    )
    is_unique = (dup.scalar() == 0)
    click = Click(link_id=link.id, ip_address=ip, is_unique=is_unique)
    db.add(click)
    if is_unique:
        link.click_count += 1
        db.add(link)
    await db.flush()

async def get_earnings_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(
            func.count(AffiliateLink.id).label("total_links"),
            func.coalesce(func.sum(AffiliateLink.click_count), 0).label("total_clicks"),
            func.coalesce(func.sum(AffiliateLink.conversion_count), 0).label("total_conversions"),
            func.coalesce(func.sum(AffiliateLink.total_earned), 0).label("total_earned"),
        ).where(AffiliateLink.user_id == user_id)
    )
    row = result.one()
    return {
        "total_links": row.total_links,
        "total_clicks": row.total_clicks,
        "total_conversions": row.total_conversions,
        "total_earned": float(row.total_earned),
    }
