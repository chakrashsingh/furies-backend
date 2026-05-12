"""
tests/test_step12.py
─────────────────────
Unit tests + curl reference for Step 12: Analytics Dashboard.
"""

from decimal import Decimal
from datetime import datetime, timezone


# ── Unit tests ────────────────────────────────────────────────────────────────

def test_date_point_schema():
    from app.schemas.analytics import DatePoint
    dp = DatePoint(date="2025-08-01", value=Decimal("149.85"))
    assert dp.date  == "2025-08-01"
    assert dp.value == Decimal("149.85")


def test_application_pipeline_total():
    from app.schemas.analytics import ApplicationPipeline
    p = ApplicationPipeline(pending=3, accepted=5, rejected=2, withdrawn=1, total=11)
    assert p.total == 11


def test_link_performance_conversion_rate():
    import uuid
    from app.schemas.analytics import LinkPerformance
    lp = LinkPerformance(
        link_id=uuid.uuid4(),
        short_code="aB3kZ9mQ",
        custom_alias="riya-vitc",
        product_name="Vitamin C Serum",
        product_id=uuid.uuid4(),
        click_count=100,
        conversion_count=12,
        total_earned=Decimal("1798.20"),
        conversion_rate=12.0,
        is_active=True,
    )
    assert lp.conversion_count == 12
    assert lp.total_earned == Decimal("1798.20")


def test_admin_summary_schema():
    from app.schemas.analytics import AdminSummary
    s = AdminSummary(
        total_users=500, total_influencers=350, total_brands=150,
        total_products=800, total_affiliate_links=1200,
        total_campaigns=45, total_events=30, total_applications=280,
        total_clicks=45000, total_conversions=3200, total_purchases=3100,
        gross_merchandise_value=Decimal("15000000.00"),
        total_commissions_paid=Decimal("1800000.00"),
        new_users_30d=42, purchases_30d=310, gmv_30d=Decimal("1500000.00"),
        generated_at=datetime.now(timezone.utc),
    )
    assert s.total_users == 500
    assert s.gross_merchandise_value == Decimal("15000000.00")


def test_window_start_returns_utc():
    from app.services.analytics_service import _window_start
    w = _window_start(30)
    assert w.tzinfo is not None
    assert (datetime.now(timezone.utc) - w).days == 30


def test_zero_decimal():
    from app.services.analytics_service import _zero_decimal
    z = _zero_decimal()
    assert z == Decimal("0.00")
    assert isinstance(z, Decimal)


def test_analytics_router_routes():
    from app.routers.analytics import router
    paths = [r.path for r in router.routes]
    assert "/analytics/influencer/dashboard"           in paths
    assert "/analytics/influencer/earnings/summary"    in paths
    assert "/analytics/influencer/links/{link_id}/earnings" in paths
    assert "/analytics/brand/dashboard"                in paths
    assert "/analytics/brand/top-influencers"          in paths
    assert "/analytics/admin/summary"                  in paths


def test_brand_dashboard_schema():
    import uuid
    from app.schemas.analytics import BrandDashboard
    bd = BrandDashboard(
        brand_id=uuid.uuid4(),
        company_name="GlowUp Skincare",
        total_products=12,
        total_campaigns=3,
        total_purchases=48,
        total_revenue=Decimal("47952.00"),
        total_commission=Decimal("7192.80"),
        revenue_30d=Decimal("9990.00"),
        purchases_30d=10,
        campaigns=[],
        top_products=[],
        top_influencers=[],
        revenue_chart=[],
    )
    assert bd.company_name == "GlowUp Skincare"
    assert bd.total_commission == Decimal("7192.80")


# ── Curl reference ────────────────────────────────────────────────────────────
"""
=== STEP 12: ANALYTICS DASHBOARD APIs ===

───────────────────────────────────
INFLUENCER ANALYTICS
───────────────────────────────────

# 1. Full influencer dashboard
curl http://localhost:8000/api/v1/analytics/influencer/dashboard \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# Response shape:
# {
#   "influencer_id": "...",
#   "full_name": "Riya Sharma",
#   "niche": "beauty",
#   "follower_count": 85000,
#   "total_clicks": 1420,
#   "total_conversions": 98,
#   "total_earnings": "14701.30",
#   "overall_conversion_rate": 6.9,
#   "clicks_30d": 342,
#   "conversions_30d": 24,
#   "earnings_30d": "3597.60",
#   "top_links": [
#     {
#       "link_id": "...",
#       "short_code": "aB3kZ9mQ",
#       "custom_alias": "riya-vitc-serum",
#       "product_name": "Vitamin C Serum 30ml",
#       "click_count": 580,
#       "conversion_count": 42,
#       "total_earned": "6287.70",
#       "conversion_rate": 7.24,
#       "is_active": true
#     }
#   ],
#   "campaign_applications": {"pending": 2, "accepted": 3, "rejected": 1, "withdrawn": 0, "total": 6},
#   "event_applications":    {"pending": 1, "accepted": 2, "rejected": 0, "withdrawn": 0, "total": 3},
#   "earnings_chart": [
#     {"date": "2025-07-22", "value": "0.00"},
#     {"date": "2025-07-23", "value": "299.70"},
#     ...30 days...
#   ],
#   "clicks_chart": [...],
#   "conversions_chart": [...],
#   "recent_purchases": [...]
# }

# 2. Quick earnings summary widget
curl http://localhost:8000/api/v1/analytics/influencer/earnings/summary \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# Response:
# {
#   "total_earnings": "14701.30",
#   "earnings_30d": "3597.60",
#   "earnings_7d": "1049.40",
#   "total_clicks": 1420,
#   "total_conversions": 98,
#   "active_links": 7
# }

# 3. Single link earnings chart (for sparkline)
curl "http://localhost:8000/api/v1/analytics/influencer/links/<LINK_ID>/earnings?days=30" \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

───────────────────────────────────
BRAND ANALYTICS
───────────────────────────────────

# 4. Full brand dashboard
curl http://localhost:8000/api/v1/analytics/brand/dashboard \
  -H "Authorization: Bearer <BRAND_TOKEN>"

# Response shape:
# {
#   "brand_id": "...",
#   "company_name": "GlowUp Skincare",
#   "total_products": 8,
#   "total_campaigns": 3,
#   "total_purchases": 142,
#   "total_revenue": "141858.00",
#   "total_commission": "21278.70",
#   "revenue_30d": "29970.00",
#   "purchases_30d": 30,
#   "campaigns": [
#     {
#       "campaign_id": "...",
#       "title": "Summer Skincare Campaign 2025",
#       "status": "open",
#       "total_applications": 18,
#       "accepted": 4,
#       "budget_amount": "25000.00"
#     }
#   ],
#   "top_products": [...],
#   "top_influencers": [
#     {
#       "influencer_id": "...",
#       "full_name": "Riya Sharma",
#       "niche": "beauty",
#       "total_conversions": 42,
#       "total_revenue": "41958.00",
#       "total_commission": "6293.70"
#     }
#   ],
#   "revenue_chart": [{"date": "2025-07-22", "value": "0.00"}, ...]
# }

# 5. Top influencers leaderboard
curl "http://localhost:8000/api/v1/analytics/brand/top-influencers?limit=10" \
  -H "Authorization: Bearer <BRAND_TOKEN>"

───────────────────────────────────
ADMIN / PLATFORM KPIs
───────────────────────────────────

# 6. Platform-wide KPI summary
curl http://localhost:8000/api/v1/analytics/admin/summary \
  -H "Authorization: Bearer <ANY_TOKEN>"

# Response:
# {
#   "total_users": 1248,
#   "total_influencers": 890,
#   "total_brands": 358,
#   "total_products": 2140,
#   "total_affiliate_links": 8730,
#   "total_campaigns": 142,
#   "total_events": 87,
#   "total_applications": 1830,
#   "total_clicks": 284000,
#   "total_conversions": 19800,
#   "total_purchases": 19600,
#   "gross_merchandise_value": "19404000.00",
#   "total_commissions_paid": "2910600.00",
#   "new_users_30d": 124,
#   "purchases_30d": 1960,
#   "gmv_30d": "1940400.00",
#   "generated_at": "2025-08-20T14:32:00Z"
# }
"""
