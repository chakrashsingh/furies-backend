"""
tests/test_step5.py
────────────────────
Unit tests + curl reference for Step 5: Affiliate Link System.
"""

# ── Unit tests ────────────────────────────────────────────────────────────────

def test_short_code_length_and_charset():
    """Generated codes must be 8 chars from [a-zA-Z0-9]."""
    import string
    from app.utils.short_code import _generate_code, _CODE_LENGTH
    allowed = set(string.ascii_letters + string.digits)
    for _ in range(100):
        code = _generate_code()
        assert len(code) == _CODE_LENGTH, f"Bad length: {len(code)}"
        assert all(c in allowed for c in code), f"Bad charset: {code}"
    print("  100 codes generated — all valid length and charset")


def test_short_code_uniqueness_distribution():
    """100 independently generated codes should all be distinct."""
    from app.utils.short_code import _generate_code
    codes = {_generate_code() for _ in range(100)}
    assert len(codes) == 100, f"Collision detected: only {len(codes)} unique codes"


def test_alias_schema_validation():
    """custom_alias must be URL-safe (no spaces or special chars)."""
    from pydantic import ValidationError
    from app.schemas.affiliate_link import AffiliateLinkCreate
    import uuid

    pid = uuid.uuid4()

    # Valid alias
    link = AffiliateLinkCreate(product_id=pid, custom_alias="riya-vitc-serum")
    assert link.custom_alias == "riya-vitc-serum"

    # Valid alias gets lowercased
    link2 = AffiliateLinkCreate(product_id=pid, custom_alias="Riya-VITC")
    assert link2.custom_alias == "riya-vitc"

    # Invalid alias — spaces
    try:
        AffiliateLinkCreate(product_id=pid, custom_alias="riya vitc")
        assert False, "Should raise"
    except ValidationError:
        pass

    # Invalid alias — special chars
    try:
        AffiliateLinkCreate(product_id=pid, custom_alias="riya@vitc!")
        assert False, "Should raise"
    except ValidationError:
        pass


def test_alias_too_short():
    from pydantic import ValidationError
    from app.schemas.affiliate_link import AffiliateLinkCreate
    import uuid
    try:
        AffiliateLinkCreate(product_id=uuid.uuid4(), custom_alias="ab")  # < 3 chars
        assert False
    except ValidationError:
        pass


# ── Curl reference ────────────────────────────────────────────────────────────
"""
=== STEP 5: AFFILIATE LINK GENERATION ===

Prerequisites:
  - Influencer is logged in → INFLUENCER_TOKEN
  - Brand has created a product → PRODUCT_ID

# 1. Generate affiliate link (no alias)
curl -X POST http://localhost:8000/api/v1/affiliate/links \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "<PRODUCT_ID>"}'

# Response:
# {
#   "id": "...",
#   "short_code": "aB3kZ9mQ",
#   "custom_alias": null,
#   "redirect_url": "http://localhost:8000/go/aB3kZ9mQ",
#   "click_count": 0,
#   "conversion_count": 0,
#   "total_earned": "0.00",
#   "is_active": true
# }

# 2. Generate affiliate link with vanity alias
curl -X POST http://localhost:8000/api/v1/affiliate/links \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "<PRODUCT_ID_2>", "custom_alias": "riya-vitc-serum"}'

# redirect_url → http://localhost:8000/go/riya-vitc-serum

# 3. List all my links with stats
curl http://localhost:8000/api/v1/affiliate/links \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 4. Pause a link
curl -X PATCH http://localhost:8000/api/v1/affiliate/links/<LINK_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# 5. Reactivate a link
curl -X PATCH http://localhost:8000/api/v1/affiliate/links/<LINK_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'

# 6. Soft-delete a link
curl -X DELETE http://localhost:8000/api/v1/affiliate/links/<LINK_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 7. Test the redirect (Step 6 wires the actual redirect logic):
curl -L http://localhost:8000/go/aB3kZ9mQ
# → 302 redirect → product landing page
# → click recorded in DB

# ERROR CASES:
# Duplicate product → 400: "You already have an affiliate link for this product."
# Alias taken       → 400: "Alias 'riya-vitc-serum' is already taken."
# Wrong role        → 403: "Access restricted. Required role(s): ['influencer']"
"""
