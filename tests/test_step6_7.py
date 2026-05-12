"""
tests/test_step6_7.py
──────────────────────
Unit tests + curl reference for Steps 6 & 7.
"""

from decimal import Decimal


# ── Step 7: Earnings calculation unit tests ───────────────────────────────────

def test_commission_exact():
    from app.services.purchase_service import _calculate_commission
    # ₹999.00 × 15% = ₹149.85
    result = _calculate_commission(Decimal("999.00"), Decimal("15.00"))
    assert result == Decimal("149.85"), f"Got {result}"


def test_commission_rounding_half_up():
    from app.services.purchase_service import _calculate_commission
    # ₹100.00 × 33.33% = ₹33.33 (rounds HALF_UP)
    result = _calculate_commission(Decimal("100.00"), Decimal("33.33"))
    assert result == Decimal("33.33"), f"Got {result}"


def test_commission_zero_pct():
    from app.services.purchase_service import _calculate_commission
    result = _calculate_commission(Decimal("500.00"), Decimal("0.00"))
    assert result == Decimal("0.00")


def test_commission_100_pct():
    from app.services.purchase_service import _calculate_commission
    result = _calculate_commission(Decimal("200.00"), Decimal("100.00"))
    assert result == Decimal("200.00")


def test_order_id_format():
    from app.services.purchase_service import _generate_order_id
    for _ in range(20):
        oid = _generate_order_id()
        assert oid.startswith("ORD-"), f"Bad prefix: {oid}"
        assert len(oid) == 12, f"Bad length: {oid} ({len(oid)})"
        suffix = oid[4:]
        assert suffix == suffix.upper(), f"Not uppercase: {suffix}"
        int(suffix, 16)   # must be valid hex


def test_session_token_length():
    from app.services.click_service import _new_session_token
    for _ in range(10):
        tok = _new_session_token()
        # secrets.token_urlsafe(32) → 43 chars
        assert len(tok) >= 40, f"Token too short: {len(tok)}"


def test_click_schema():
    from app.schemas.click import ClickStats
    stats = ClickStats(
        affiliate_link_id=__import__("uuid").uuid4(),
        total_clicks=100,
        unique_clicks=80,
        conversions=10,
        conversion_rate=12.5,
    )
    assert stats.conversion_rate == 12.5


def test_purchase_schema_defaults():
    from app.schemas.purchase import MockPurchaseRequest
    import uuid
    req = MockPurchaseRequest(product_id=uuid.uuid4())
    assert req.quantity == 1
    assert req.session_token is None
    assert req.override_amount is None


# ── Curl reference ────────────────────────────────────────────────────────────
"""
=== STEP 6: CLICK TRACKING ===

# 1. Visit affiliate link → triggers click record + redirect
#    (use -v to see response headers, -L to follow redirect)
curl -v http://localhost:8000/go/aB3kZ9mQ

# Response: HTTP 302 → Location: https://product.com/landing?aff_session=<TOKEN>
# The aff_session token is what you need for step 7.

# 2. Visit a vanity alias
curl -v http://localhost:8000/go/riya-vitc-serum

# 3. Inactive link → 410 Gone
curl -v http://localhost:8000/go/pausedLinkCode

# 4. Non-existent link → 404
curl -v http://localhost:8000/go/doesnotexist

# 5. View click stats for a link (influencer only)
curl http://localhost:8000/api/v1/clicks/<LINK_ID>/stats \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"
# Response:
# {
#   "affiliate_link_id": "...",
#   "total_clicks": 47,
#   "unique_clicks": 38,
#   "conversions": 5,
#   "conversion_rate": 13.16
# }

# 6. View raw click history
curl "http://localhost:8000/api/v1/clicks/<LINK_ID>/history?limit=20&offset=0" \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"


=== STEP 7: MOCK PURCHASE + CONVERSION ATTRIBUTION ===

# 1. Attributed purchase (with session_token from redirect)
curl -X POST http://localhost:8000/api/v1/purchases/mock \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "<PRODUCT_ID>",
    "session_token": "<TOKEN_FROM_REDIRECT>",
    "buyer_name": "Priya Patel",
    "buyer_email": "priya@example.com",
    "quantity": 1
  }'
# Response:
# {
#   "id": "...",
#   "purchase_amount": "999.00",
#   "commission_pct": "15.00",
#   "commission_amount": "149.85",       ← ₹999 × 15%
#   "status": "confirmed",
#   "attribution": "attributed",         ← influencer credited
#   "influencer_id": "...",
#   "order_id": "ORD-3FA2C1B8"
# }

# 2. Unattributed purchase (no session_token — direct buy, no commission)
curl -X POST http://localhost:8000/api/v1/purchases/mock \
  -H "Content-Type: application/json" \
  -d '{"product_id": "<PRODUCT_ID>", "buyer_name": "Direct Buyer"}'
# → attribution: "none", commission_amount: "0.00"

# 3. Multi-unit purchase with price override
curl -X POST http://localhost:8000/api/v1/purchases/mock \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "<PRODUCT_ID>",
    "session_token": "<TOKEN>",
    "quantity": 3,
    "override_amount": "2500.00"
  }'
# → commission = ₹2500 × 15% = ₹375.00

# 4. View influencer earnings history
curl http://localhost:8000/api/v1/purchases/my/history \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 5. View purchases per affiliate link
curl http://localhost:8000/api/v1/purchases/link/<LINK_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 6. After purchase — check dashboard (earnings updated live)
curl http://localhost:8000/api/v1/influencers/me \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"
# → total_earnings, total_conversions incremented
"""
