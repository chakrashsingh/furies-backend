"""
app/schemas/analytics.py
─────────────────────────
Response schemas for all analytics dashboard endpoints.

Three dashboards, one module:
    1. InfluencerDashboard  — earnings, clicks, conversions, link breakdown,
                              time-series, application pipeline
    2. BrandDashboard       — total spend, conversions, product performance,
                              campaign overview, top influencers
    3. AdminSummary         — platform-wide KPIs (users, GMV, commissions paid)

All monetary values are Decimal — never float (no rounding errors).
All time-series use ISO date strings so the frontend can plot directly.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from app.models.application import ApplicationStatus
from app.models.campaign import CampaignStatus


# ─────────────────────────────────────────────────────────────────────────────
# Shared primitives
# ─────────────────────────────────────────────────────────────────────────────

class DatePoint(BaseModel):
    """One data point in a time-series chart."""
    date:  str      # ISO date string "2025-08-01"
    value: Decimal


class LinkPerformance(BaseModel):
    """Per-link performance summary inside the influencer dashboard."""
    link_id:          uuid.UUID
    short_code:       str
    custom_alias:     Optional[str]
    product_name:     str
    product_id:       uuid.UUID
    click_count:      int
    conversion_count: int
    total_earned:     Decimal
    conversion_rate:  float          # conversions / unique_clicks × 100
    is_active:        bool


class ApplicationPipeline(BaseModel):
    """Count of applications by status — for the influencer's overview."""
    pending:   int
    accepted:  int
    rejected:  int
    withdrawn: int
    total:     int


# ─────────────────────────────────────────────────────────────────────────────
# Influencer Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class InfluencerDashboard(BaseModel):
    """
    Complete influencer analytics dashboard.
    Returned by GET /api/v1/analytics/influencer/dashboard
    """
    # ── Identity ──────────────────────────────────────────────────────────────
    influencer_id:   uuid.UUID
    full_name:       str
    niche:           str
    follower_count:  int

    # ── All-time totals (from denormalised counters — O(1) reads) ─────────────
    total_clicks:      int
    total_conversions: int
    total_earnings:    Decimal
    overall_conversion_rate: float   # total_conversions / total_clicks × 100

    # ── Period totals (last 30 days, computed live) ───────────────────────────
    clicks_30d:      int
    conversions_30d: int
    earnings_30d:    Decimal

    # ── Best performers ───────────────────────────────────────────────────────
    top_links:       List[LinkPerformance]   # top 5 by earnings
    recent_links:    List[LinkPerformance]   # 5 most recently created

    # ── Application pipeline ──────────────────────────────────────────────────
    campaign_applications: ApplicationPipeline
    event_applications:    ApplicationPipeline

    # ── Earnings time-series (last 30 days, one point per day) ───────────────
    earnings_chart:    List[DatePoint]
    clicks_chart:      List[DatePoint]
    conversions_chart: List[DatePoint]

    # ── Recent purchases that earned commission ───────────────────────────────
    recent_purchases: List[dict]   # lightweight — id, amount, commission, date


# ─────────────────────────────────────────────────────────────────────────────
# Brand Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class ProductPerformance(BaseModel):
    """Per-product sales + commission data for brand analytics."""
    product_id:        uuid.UUID
    product_name:      str
    total_purchases:   int
    total_revenue:     Decimal
    total_commission:  Decimal        # what brand has paid to influencers
    affiliate_links:   int            # how many links exist for this product


class TopInfluencer(BaseModel):
    """An influencer ranked by sales driven for a specific brand."""
    influencer_id:    uuid.UUID
    full_name:        str
    niche:            str
    total_conversions: int
    total_revenue:    Decimal
    total_commission: Decimal


class CampaignStat(BaseModel):
    """Campaign overview row for brand dashboard."""
    campaign_id:       uuid.UUID
    title:             str
    status:            CampaignStatus
    total_applications: int
    accepted:          int
    budget_amount:     Optional[Decimal]
    created_at:        datetime


class BrandDashboard(BaseModel):
    """
    Complete brand analytics dashboard.
    Returned by GET /api/v1/analytics/brand/dashboard
    """
    # ── Identity ──────────────────────────────────────────────────────────────
    brand_id:     uuid.UUID
    company_name: str

    # ── All-time totals ───────────────────────────────────────────────────────
    total_products:    int
    total_campaigns:   int
    total_purchases:   int
    total_revenue:     Decimal     # sum of all purchase_amounts
    total_commission:  Decimal     # sum of all commission_amounts paid out

    # ── 30-day window ─────────────────────────────────────────────────────────
    revenue_30d:    Decimal
    purchases_30d:  int

    # ── Campaign pipeline ─────────────────────────────────────────────────────
    campaigns:      List[CampaignStat]

    # ── Product performance ───────────────────────────────────────────────────
    top_products:   List[ProductPerformance]   # top 5 by revenue

    # ── Top influencers driving sales ─────────────────────────────────────────
    top_influencers: List[TopInfluencer]       # top 5 by conversions

    # ── Revenue time-series (last 30 days) ────────────────────────────────────
    revenue_chart:  List[DatePoint]


# ─────────────────────────────────────────────────────────────────────────────
# Platform Admin Summary
# ─────────────────────────────────────────────────────────────────────────────

class AdminSummary(BaseModel):
    """
    Platform-wide KPIs.
    Returned by GET /api/v1/analytics/admin/summary
    In production, lock this behind an ADMIN role.
    For MVP it requires brand OR influencer auth as a placeholder.
    """
    # ── User counts ───────────────────────────────────────────────────────────
    total_users:       int
    total_influencers: int
    total_brands:      int

    # ── Content ───────────────────────────────────────────────────────────────
    total_products:       int
    total_affiliate_links: int
    total_campaigns:      int
    total_events:         int
    total_applications:   int

    # ── Transaction KPIs ──────────────────────────────────────────────────────
    total_clicks:      int
    total_conversions: int
    total_purchases:   int
    gross_merchandise_value: Decimal    # sum of all purchase_amounts
    total_commissions_paid:  Decimal    # sum of all commission_amounts

    # ── 30-day activity ───────────────────────────────────────────────────────
    new_users_30d:     int
    purchases_30d:     int
    gmv_30d:           Decimal

    generated_at: datetime
