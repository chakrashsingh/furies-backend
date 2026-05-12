"""
app/services/credibility_service.py
─────────────────────────────────────
Credibility Score Engine — Feature 3.

Scores an influencer 0–100 based on signals we can verify
without calling any external API.

SCORING BREAKDOWN (total = 100 points):
────────────────────────────────────────
1. Engagement Rate Check          25 pts
   (avg_likes + avg_comments) / followers × 100
   Industry benchmarks:
     < 1%   → 5 pts   (likely inflated following)
     1–3%   → 13 pts  (average)
     3–6%   → 20 pts  (good)
     > 6%   → 25 pts  (excellent)

2. Follower-to-Following Ratio    15 pts
   Real influencers are followed by far more than they follow.
   We use follower_count as proxy (no API needed):
     0–1k      → 3  pts  (too early to judge)
     1k–10k    → 8  pts  (micro)
     10k–100k  → 12 pts  (mid-tier)
     100k+     → 15 pts  (macro/established)

3. Platform Conversion Rate       35 pts  ← STRONGEST SIGNAL
   Real purchases driven on Furies — impossible to fake.
   No conversion history yet → 10 pts (neutral, not penalised)
   Conv rate 0–0.5%          → 15 pts
   Conv rate 0.5–1%          → 22 pts
   Conv rate 1–3%            → 28 pts
   Conv rate > 3%            → 35 pts

4. Profile Completeness           15 pts
   Checks: bio, niche set, payment details, social handle(s),
   verified flag.
   1 pt per completed field, capped at 15.

5. Account Stability               10 pts
   How long the influencer has been on Furies platform.
   < 7 days    → 2  pts
   7–30 days   → 5  pts
   30–90 days  → 8  pts
   > 90 days   → 10 pts

BADGES (derived from score):
    90–100 → "Elite"       🏆
    75–89  → "Verified"    ✅
    50–74  → "Rising"      📈
    25–49  → "New"         🌱
    0–24   → "Unverified"  ⚠️
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from app.models.influencer import InfluencerProfile


# ─────────────────────────────────────────────────────────────────────────────
# Scoring functions (pure — no DB calls, just the ORM object)
# ─────────────────────────────────────────────────────────────────────────────

def _score_engagement(inf: InfluencerProfile) -> tuple[int, str]:
    """Returns (points, explanation)."""
    rate = float(inf.avg_engagement_rate or 0)
    if rate >= 6:
        return 25, f"Excellent engagement rate: {rate:.1f}%"
    elif rate >= 3:
        return 20, f"Good engagement rate: {rate:.1f}%"
    elif rate >= 1:
        return 13, f"Average engagement rate: {rate:.1f}%"
    elif rate > 0:
        return 5,  f"Low engagement rate: {rate:.1f}% — possible inflated following"
    else:
        return 0,  "No engagement rate provided"


def _score_follower_tier(inf: InfluencerProfile) -> tuple[int, str]:
    """Returns (points, explanation)."""
    f = inf.follower_count or 0
    if f >= 100_000:
        return 15, f"Macro influencer: {f:,} followers"
    elif f >= 10_000:
        return 12, f"Mid-tier: {f:,} followers"
    elif f >= 1_000:
        return 8,  f"Micro influencer: {f:,} followers"
    else:
        return 3,  f"Early stage: {f:,} followers"


def _score_conversion(inf: InfluencerProfile) -> tuple[int, str]:
    """Returns (points, explanation). Uses denormalised counters — O(1)."""
    clicks = inf.total_clicks or 0
    convs  = inf.total_conversions or 0

    if clicks == 0:
        return 10, "No conversion history yet (neutral score)"

    rate = (convs / clicks) * 100
    if rate > 3:
        return 35, f"Outstanding conversion rate: {rate:.2f}% ({convs} sales from {clicks:,} clicks)"
    elif rate >= 1:
        return 28, f"Strong conversion rate: {rate:.2f}%"
    elif rate >= 0.5:
        return 22, f"Good conversion rate: {rate:.2f}%"
    elif rate > 0:
        return 15, f"Low conversion rate: {rate:.2f}%"
    else:
        return 8,  f"Zero conversions from {clicks:,} clicks"


def _score_completeness(inf: InfluencerProfile) -> tuple[int, str]:
    """Returns (points, explanation). Each completed field = 1 pt, max 15."""
    checks = [
        (bool(inf.niche),           "Niche set"),
        (inf.follower_count > 0,    "Follower count set"),
        (inf.avg_engagement_rate > 0, "Engagement rate set"),
        (bool(inf.bio),             "Bio written"),
        (bool(inf.instagram_handle),"Instagram handle"),
        (bool(inf.youtube_channel), "YouTube channel"),
        (bool(inf.twitter_handle),  "Twitter handle"),
        (bool(inf.payment_method),  "Payment method set"),
        (bool(inf.upi_id) or bool(inf.bank_account_no), "Payment details"),
        (inf.is_verified,           "Platform verified"),
    ]
    earned     = sum(1 for passed, _ in checks if passed)
    completed  = [label for passed, label in checks if passed]
    missing    = [label for passed, label in checks if not passed]
    pts        = min(earned + 5, 15)   # base 5 pts + 1 per field, max 15
    detail     = f"{earned}/10 profile fields complete"
    return pts, detail


def _score_account_age(inf: InfluencerProfile) -> tuple[int, str]:
    """Returns (points, explanation). Based on profile created_at."""
    now  = datetime.now(timezone.utc)
    age  = now - inf.created_at
    days = age.days

    if days > 90:
        return 10, f"Established account: {days} days on platform"
    elif days > 30:
        return 8,  f"Growing account: {days} days on platform"
    elif days > 7:
        return 5,  f"New account: {days} days on platform"
    else:
        return 2,  f"Very new account: {days} days on platform"


def compute_score(inf: InfluencerProfile) -> int:
    """
    Main entry point — compute and return integer score 0–100.
    Pure function: takes ORM object, returns int.
    """
    pts_eng,  _ = _score_engagement(inf)
    pts_tier, _ = _score_follower_tier(inf)
    pts_conv, _ = _score_conversion(inf)
    pts_comp, _ = _score_completeness(inf)
    pts_age,  _ = _score_account_age(inf)
    return min(pts_eng + pts_tier + pts_conv + pts_comp + pts_age, 100)


def get_badge(score: int) -> tuple[str, str]:
    """Returns (badge_name, emoji)."""
    if score >= 90:
        return "Elite",      "🏆"
    elif score >= 75:
        return "Verified",   "✅"
    elif score >= 50:
        return "Rising",     "📈"
    elif score >= 25:
        return "New",        "🌱"
    else:
        return "Unverified", "⚠️"


def get_full_report(inf: InfluencerProfile) -> dict:
    """
    Full credibility report with breakdown per dimension.
    Returned by GET /api/v1/credibility/{influencer_id}
    """
    eng_pts,  eng_note  = _score_engagement(inf)
    tier_pts, tier_note = _score_follower_tier(inf)
    conv_pts, conv_note = _score_conversion(inf)
    comp_pts, comp_note = _score_completeness(inf)
    age_pts,  age_note  = _score_account_age(inf)

    total = min(eng_pts + tier_pts + conv_pts + comp_pts + age_pts, 100)
    badge_name, badge_emoji = get_badge(total)

    return {
        "influencer_id":   str(inf.id),
        "total_score":     total,
        "badge":           badge_name,
        "badge_emoji":     badge_emoji,
        "breakdown": {
            "engagement_rate": {
                "points": eng_pts,
                "max":    25,
                "note":   eng_note,
            },
            "follower_tier": {
                "points": tier_pts,
                "max":    15,
                "note":   tier_note,
            },
            "platform_conversions": {
                "points": conv_pts,
                "max":    35,
                "note":   conv_note,
            },
            "profile_completeness": {
                "points": comp_pts,
                "max":    15,
                "note":   comp_note,
            },
            "account_stability": {
                "points": age_pts,
                "max":    10,
                "note":   age_note,
            },
        },
        "what_would_improve_score": _improvement_tips(
            eng_pts, tier_pts, conv_pts, comp_pts, age_pts
        ),
        "raw_signals": {
            "follower_count":       inf.follower_count,
            "avg_engagement_rate":  float(inf.avg_engagement_rate or 0),
            "total_clicks":         inf.total_clicks,
            "total_conversions":    inf.total_conversions,
            "total_earnings":       str(inf.total_earnings),
            "is_verified":          inf.is_verified,
        },
    }


def _improvement_tips(eng, tier, conv, comp, age) -> list[str]:
    """Actionable tips for low-scoring dimensions."""
    tips = []
    if eng < 13:
        tips.append("Set your avg_engagement_rate on your influencer profile "
                    "— even self-reported data helps brands trust you")
    if conv < 22:
        tips.append("Generate affiliate links and drive real purchases — "
                    "conversion data is our strongest trust signal")
    if comp < 12:
        tips.append("Complete your profile: add bio, social handles, "
                    "payment method, and engagement rate")
    if age < 8:
        tips.append("Keep using the platform — account stability score "
                    "increases automatically over time")
    return tips
