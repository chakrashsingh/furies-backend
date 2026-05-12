"""
tests/test_step3_4.py
──────────────────────
Unit tests + curl reference for Steps 3 & 4.
"""

# ── Schema unit tests ─────────────────────────────────────────────────────────

def test_influencer_schema_upi_validation():
    from pydantic import ValidationError
    from app.schemas.influencer import InfluencerProfileCreate
    try:
        InfluencerProfileCreate(
            niche="fashion", follower_count=10000,
            upi_id="invaliddnouatsign"  # missing @
        )
        assert False, "Should raise"
    except ValidationError:
        pass

def test_influencer_schema_valid():
    from app.schemas.influencer import InfluencerProfileCreate
    p = InfluencerProfileCreate(
        bio="Lifestyle creator", niche="lifestyle",
        follower_count=50000, upi_id="riya@okaxis"
    )
    assert p.niche == "lifestyle"
    assert p.upi_id == "riya@okaxis"

def test_product_schema_commission_bounds():
    from pydantic import ValidationError
    from app.schemas.product import ProductCreate
    from decimal import Decimal
    try:
        ProductCreate(name="Test", price=Decimal("100"), commission_pct=Decimal("110"))
        assert False, "commission > 100 should raise"
    except ValidationError:
        pass

def test_product_schema_valid():
    from app.schemas.product import ProductCreate
    from decimal import Decimal
    p = ProductCreate(
        name="Vitamin C Serum",
        price=Decimal("999.00"),
        commission_pct=Decimal("15.00"),
        product_type="physical",
    )
    assert p.commission_pct == Decimal("15.00")


# ── Curl reference payloads ───────────────────────────────────────────────────

"""
=== STEP 3: INFLUENCER PROFILE ===

# 1. Signup as influencer (get token)
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Riya Sharma","email":"riya@example.com","password":"Str0ngPass1","role":"influencer"}'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"riya@example.com","password":"Str0ngPass1"}'

# 3. Create influencer profile
curl -X POST http://localhost:8000/api/v1/influencers/profile \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "bio": "Skincare & lifestyle creator from Mumbai",
    "niche": "beauty",
    "instagram_handle": "@riyaskincare",
    "follower_count": 85000,
    "avg_engagement_rate": 4.20,
    "payment_method": "upi",
    "upi_id": "riya@okaxis"
  }'

# 4. View own dashboard
curl http://localhost:8000/api/v1/influencers/me \
  -H "Authorization: Bearer <TOKEN>"

# 5. Browse influencer directory (public)
curl "http://localhost:8000/api/v1/influencers/?niche=beauty&min_followers=10000"


=== STEP 3: BRAND PROFILE ===

# 1. Signup as brand
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Arjun Mehta","email":"arjun@skinbrand.com","password":"Brand0Pass1","role":"brand"}'

# 2. Create brand profile
curl -X POST http://localhost:8000/api/v1/brands/profile \
  -H "Authorization: Bearer <BRAND_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "GlowUp Skincare",
    "company_website": "https://glowup.in",
    "industry": "beauty",
    "description": "Premium skincare for Indian skin types",
    "contact_email": "collab@glowup.in",
    "gst_number": "27AAPFU0939F1ZV"
  }'


=== STEP 4: PRODUCTS ===

# 1. Brand creates a product
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer <BRAND_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Vitamin C Serum 30ml",
    "description": "Brightening serum with 15% Vitamin C",
    "product_type": "physical",
    "price": 999.00,
    "commission_pct": 15.00,
    "product_url": "https://glowup.in/products/vit-c-serum"
  }'

# 2. Browse all products (public)
curl "http://localhost:8000/api/v1/products/?product_type=physical"

# 3. Soft-delete a product
curl -X DELETE http://localhost:8000/api/v1/products/<PRODUCT_ID> \
  -H "Authorization: Bearer <BRAND_TOKEN>"
"""
