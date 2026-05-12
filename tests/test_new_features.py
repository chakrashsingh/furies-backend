"""
tests/test_new_features.py
───────────────────────────
Unit tests for Portfolio, Search, and Credibility Score.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta


# ── Feature 3: Credibility Score ──────────────────────────────────────────────

class MockInfluencer:
    """Minimal mock of InfluencerProfile for unit testing the score engine."""
    def __init__(self, **kwargs):
        self.id                 = uuid.uuid4()
        self.niche              = type("N", (), {"value": "beauty"})()
        self.follower_count     = kwargs.get("follower_count", 0)
        self.avg_engagement_rate= Decimal(str(kwargs.get("avg_engagement_rate", 0)))
        self.total_clicks       = kwargs.get("total_clicks", 0)
        self.total_conversions  = kwargs.get("total_conversions", 0)
        self.total_earnings     = Decimal(str(kwargs.get("total_earnings", 0)))
        self.bio                = kwargs.get("bio", "A creator")
        self.instagram_handle   = kwargs.get("instagram_handle", "@test")
        self.youtube_channel    = kwargs.get("youtube_channel", None)
        self.twitter_handle     = kwargs.get("twitter_handle", None)
        self.payment_method     = kwargs.get("payment_method", "upi")
        self.upi_id             = kwargs.get("upi_id", "test@upi")
        self.bank_account_no    = None
        self.is_verified        = kwargs.get("is_verified", False)
        days_ago                = kwargs.get("days_on_platform", 60)
        self.created_at         = datetime.now(timezone.utc) - timedelta(days=days_ago)


def test_score_is_integer_0_to_100():
    from app.services.credibility_service import compute_score
    for scenario in [
        MockInfluencer(),   # empty
        MockInfluencer(follower_count=100000, avg_engagement_rate=5.0,
                       total_clicks=5000, total_conversions=200),
        MockInfluencer(follower_count=1000, avg_engagement_rate=0.1),
    ]:
        score = compute_score(scenario)
        assert isinstance(score, int), f"Expected int, got {type(score)}"
        assert 0 <= score <= 100, f"Score {score} out of range"


def test_high_engagement_scores_more():
    from app.services.credibility_service import _score_engagement
    low  = MockInfluencer(avg_engagement_rate=0.5)
    high = MockInfluencer(avg_engagement_rate=7.0)
    low_pts,  _ = _score_engagement(low)
    high_pts, _ = _score_engagement(high)
    assert high_pts > low_pts, f"{high_pts} should be > {low_pts}"


def test_conversion_rate_drives_score():
    from app.services.credibility_service import _score_conversion
    no_conv   = MockInfluencer(total_clicks=1000, total_conversions=0)
    good_conv = MockInfluencer(total_clicks=1000, total_conversions=30)
    no_pts,   _ = _score_conversion(no_conv)
    good_pts, _ = _score_conversion(good_conv)
    assert good_pts > no_pts, f"Good conv ({good_pts}) should beat no conv ({no_pts})"


def test_badge_thresholds():
    from app.services.credibility_service import get_badge
    assert get_badge(95)[0] == "Elite"
    assert get_badge(80)[0] == "Verified"
    assert get_badge(60)[0] == "Rising"
    assert get_badge(35)[0] == "New"
    assert get_badge(10)[0] == "Unverified"


def test_full_report_structure():
    from app.services.credibility_service import get_full_report
    inf    = MockInfluencer(follower_count=85000, avg_engagement_rate=4.2,
                            total_clicks=1000, total_conversions=8,
                            days_on_platform=47)
    report = get_full_report(inf)
    assert "total_score"  in report
    assert "badge"        in report
    assert "breakdown"    in report
    assert "raw_signals"  in report
    dims = report["breakdown"]
    assert all(k in dims for k in [
        "engagement_rate", "follower_tier",
        "platform_conversions", "profile_completeness", "account_stability"
    ])
    for dim, data in dims.items():
        assert data["points"] <= data["max"], \
            f"{dim}: {data['points']} > max {data['max']}"


def test_improvement_tips_returned_for_new_user():
    from app.services.credibility_service import get_full_report
    inf    = MockInfluencer(days_on_platform=2)
    report = get_full_report(inf)
    assert isinstance(report["what_would_improve_score"], list)
    assert len(report["what_would_improve_score"]) > 0


# ── Feature 1: Portfolio Schemas ──────────────────────────────────────────────

def test_physical_stats_schema_height_bounds():
    from pydantic import ValidationError
    from app.schemas.portfolio import PhysicalStatsCreate
    # Valid
    s = PhysicalStatsCreate(height_cm=173, weight_kg=Decimal("58.5"))
    assert s.height_cm == 173

    # Too short
    try:
        PhysicalStatsCreate(height_cm=50)
        assert False, "Should raise"
    except ValidationError:
        pass


def test_portfolio_create_schema():
    from app.schemas.portfolio import PortfolioCreate
    p = PortfolioCreate(
        display_name="Riya Sharma",
        tagline="Fashion model & lifestyle creator",
        industry_type="fashion",
        city="Mumbai",
        country="India",
    )
    assert p.display_name == "Riya Sharma"
    assert p.industry_type.value == "fashion"


def test_custom_field_schema():
    from app.schemas.portfolio import CustomFieldCreate
    f = CustomFieldCreate(
        field_name="Certifications",
        field_value="ACE CPT, Nutrition Coach",
    )
    assert f.is_public == True
    assert f.display_order == 0


def test_portfolio_item_types():
    from app.models.portfolio import PortfolioItemType
    assert PortfolioItemType.IMAGE.value       == "image"
    assert PortfolioItemType.VIDEO_LINK.value  == "video_link"
    assert PortfolioItemType.BRAND_COLLAB.value == "brand_collab"


# ── Feature 2: Search ─────────────────────────────────────────────────────────

def test_match_reason_campaign():
    from app.services.search_service import _campaign_match_reason
    class MockCampaign:
        target_niches  = "beauty,lifestyle"
        min_followers  = 10000
        budget_amount  = Decimal("25000")
    reason = _campaign_match_reason(MockCampaign(), "beauty", 85000)
    assert "beauty" in reason
    assert "follower" in reason.lower() or "qualify" in reason.lower() or "10,000" in reason


def test_match_reason_event_virtual():
    from app.services.search_service import _event_match_reason
    class MockEvent:
        min_followers  = 5000
        location_city  = "Delhi"
        is_virtual     = True
    reason = _event_match_reason(MockEvent(), 85000, "Mumbai")
    assert "virtual" in reason.lower()


def test_search_router_routes():
    from app.routers.search import router
    paths = [r.path for r in router.routes]
    assert "/search/influencers"   in paths
    assert "/search/opportunities" in paths


def test_credibility_router_routes():
    from app.routers.credibility import router
    paths = [r.path for r in router.routes]
    assert "/credibility/me"               in paths
    assert "/credibility/{influencer_id}"  in paths


def test_portfolio_router_routes():
    from app.routers.portfolio import router
    paths = [r.path for r in router.routes]
    expected = [
        "/portfolio/",
        "/portfolio/me",
        "/portfolio/me/publish",
        "/portfolio/me/items",
        "/portfolio/me/physical-stats",
        "/portfolio/me/creator-stats",
        "/portfolio/me/custom-fields",
        "/portfolio/me/generate-pdf",
        "/portfolio/me/download-pdf",
        "/portfolio/browse",
        "/portfolio/{portfolio_id}",
    ]
    for path in expected:
        assert path in paths, f"Missing route: {path}"
