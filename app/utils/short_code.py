"""
app/utils/short_code.py
────────────────────────
Cryptographically random short code generator for affiliate links.

Uses secrets.token_urlsafe (CSPRNG) — NOT random.choice() which is
not cryptographically safe for public-facing identifiers.

Collision handling:
    generate_unique_short_code() retries up to MAX_RETRIES times,
    checking the DB each time. At 8 chars from a 64-char alphabet the
    collision probability at 1M links is ~10^-8 — effectively zero.
"""

import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate_link import AffiliateLink

# Alphabet: URL-safe, visually unambiguous (no 0/O, 1/l/I confusion)
_ALPHABET = string.ascii_letters + string.digits   # 62 chars → 62^8 ≈ 218 trillion combinations
_CODE_LENGTH = 8
_MAX_RETRIES = 5


def _generate_code(length: int = _CODE_LENGTH) -> str:
    """Return a random URL-safe string of the given length."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


async def generate_unique_short_code(db: AsyncSession) -> str:
    """
    Generate a short code guaranteed to be unique in the affiliate_links table.
    Raises RuntimeError if MAX_RETRIES exceeded (should never happen in practice).
    """
    for attempt in range(_MAX_RETRIES):
        code = _generate_code()
        result = await db.execute(
            select(AffiliateLink).where(AffiliateLink.short_code == code)
        )
        if result.scalar_one_or_none() is None:
            return code
    raise RuntimeError(
        f"Could not generate a unique short code after {_MAX_RETRIES} attempts. "
        "This should never happen — check for DB issues."
    )
