"""
tests/test_step9_10_11.py
──────────────────────────
Unit tests + curl reference for Steps 9, 10, 11.
"""

# ── Unit tests ────────────────────────────────────────────────────────────────

def test_campaign_schema_defaults():
    from app.schemas.campaign import CampaignCreate
    from decimal import Decimal
    c = CampaignCreate(
        title="Summer Skincare Campaign",
        budget_amount=Decimal("25000.00"),
    )
    assert c.campaign_type.value == "paid"
    assert c.min_followers == 0
    assert c.currency == "INR"


def test_event_schema_defaults():
    from app.schemas.event import EventCreate
    e = EventCreate(title="Sharma Wedding")
    assert e.location_country == "India"
    assert e.influencers_needed == 1
    assert e.is_virtual == False


def test_application_schema_create():
    import uuid
    from app.schemas.application import ApplicationCreate
    # Campaign application
    a = ApplicationCreate(
        campaign_id=uuid.uuid4(),
        cover_letter="I am perfect for this.",
    )
    assert a.event_id is None

    # Event application
    b = ApplicationCreate(
        event_id=uuid.uuid4(),
        proposed_rate=__import__("decimal").Decimal("10000.00"),
    )
    assert b.campaign_id is None


def test_application_decision_only_accepts_valid_statuses():
    from pydantic import ValidationError
    from app.schemas.application import ApplicationDecision
    from app.models.application import ApplicationStatus

    # Valid
    d = ApplicationDecision(status=ApplicationStatus.ACCEPTED)
    assert d.status == ApplicationStatus.ACCEPTED

    # Invalid value
    try:
        ApplicationDecision(status="maybe")
        assert False, "Should raise"
    except ValidationError:
        pass


def test_campaign_status_enum():
    from app.models.campaign import CampaignStatus
    assert CampaignStatus.DRAFT.value   == "draft"
    assert CampaignStatus.OPEN.value    == "open"
    assert CampaignStatus.CLOSED.value  == "closed"


def test_application_type_enum():
    from app.models.application import ApplicationType
    assert ApplicationType.CAMPAIGN.value == "campaign"
    assert ApplicationType.EVENT.value    == "event"


def test_event_category_enum():
    from app.models.event import EventCategory
    assert EventCategory.WEDDING.value         == "wedding"
    assert EventCategory.ORGANIZER_COLLAB.value == "organizer_collab"


# ── Curl reference ────────────────────────────────────────────────────────────
"""
=== STEP 9: CAMPAIGN SYSTEM ===

# 1. Brand creates a campaign (starts as DRAFT)
curl -X POST http://localhost:8000/api/v1/campaigns/ \
  -H "Authorization: Bearer <BRAND_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Summer Skincare Campaign 2025",
    "description": "Promote our Vitamin C range to beauty audiences.",
    "campaign_type": "paid",
    "budget_amount": 25000.00,
    "target_niches": "beauty,skincare,lifestyle",
    "min_followers": 10000,
    "max_influencers": 5,
    "deliverables": "2 Instagram Reels + 3 Stories + 1 YouTube review",
    "application_deadline": "2025-09-30T23:59:00Z",
    "campaign_start": "2025-10-15T00:00:00Z"
  }'

# 2. Publish campaign (DRAFT → OPEN)
curl -X POST http://localhost:8000/api/v1/campaigns/<CAMPAIGN_ID>/publish \
  -H "Authorization: Bearer <BRAND_TOKEN>"

# 3. Browse open campaigns (public)
curl "http://localhost:8000/api/v1/campaigns/?niche=beauty&my_followers=85000"

# 4. Brand views their own campaigns
curl http://localhost:8000/api/v1/campaigns/my/campaigns \
  -H "Authorization: Bearer <BRAND_TOKEN>"

# 5. Brand views applications received
curl http://localhost:8000/api/v1/campaigns/<CAMPAIGN_ID>/applications \
  -H "Authorization: Bearer <BRAND_TOKEN>"

# 6. Brand accepts an application
curl -X POST \
  http://localhost:8000/api/v1/campaigns/<CAMPAIGN_ID>/applications/<APP_ID>/decide \
  -H "Authorization: Bearer <BRAND_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted", "decision_note": "Great fit! We will DM you with next steps."}'

# 7. Brand rejects an application
curl -X POST \
  http://localhost:8000/api/v1/campaigns/<CAMPAIGN_ID>/applications/<APP_ID>/decide \
  -H "Authorization: Bearer <BRAND_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"status": "rejected", "decision_note": "Looking for creators with 50k+ followers."}'


=== STEP 10: EVENT HIRING SYSTEM ===

# 1. Normal user posts a wedding event
curl -X POST http://localhost:8000/api/v1/events/ \
  -H "Authorization: Bearer <USER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sharma Wedding Reception",
    "description": "Looking for lifestyle influencers to attend and cover our reception.",
    "event_category": "wedding",
    "collab_type": "paid",
    "location_city": "Mumbai",
    "location_state": "Maharashtra",
    "location_venue": "Taj Mahal Palace Hotel",
    "budget_min": 10000.00,
    "budget_max": 25000.00,
    "required_niches": "lifestyle,fashion",
    "min_followers": 20000,
    "influencers_needed": 3,
    "deliverables": "5 Instagram posts + Stories on event day",
    "event_date": "2025-12-15T18:00:00Z",
    "application_deadline": "2025-11-30T23:59:00Z"
  }'

# 2. Organizer posts a collab invite
curl -X POST http://localhost:8000/api/v1/events/ \
  -H "Authorization: Bearer <ORGANIZER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Mumbai Fashion Week - Social Media Coverage",
    "event_category": "organizer_collab",
    "collab_type": "paid",
    "location_city": "Mumbai",
    "budget_min": 20000.00,
    "budget_max": 50000.00,
    "min_followers": 50000,
    "influencers_needed": 10,
    "event_date": "2026-02-01T10:00:00Z"
  }'

# 3. Browse open events (public, filtered)
curl "http://localhost:8000/api/v1/events/?city=Mumbai&collab_type=paid&my_followers=85000"

# 4. Host views applications + decides
curl http://localhost:8000/api/v1/events/<EVENT_ID>/applications \
  -H "Authorization: Bearer <HOST_TOKEN>"

curl -X POST \
  http://localhost:8000/api/v1/events/<EVENT_ID>/applications/<APP_ID>/decide \
  -H "Authorization: Bearer <HOST_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted", "decision_note": "Looking forward to having you!"}'


=== STEP 11: APPLICATION SYSTEM (INFLUENCER SIDE) ===

# 1. Apply to a campaign
curl -X POST http://localhost:8000/api/v1/applications/campaign/<CAMPAIGN_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "cover_letter": "Hi! I reach 85k beauty enthusiasts on Instagram with 4.2% engagement...",
    "proposed_rate": 18000.00,
    "portfolio_url": "https://drive.google.com/my-media-kit"
  }'

# 2. Apply to an event
curl -X POST http://localhost:8000/api/v1/applications/event/<EVENT_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "cover_letter": "I would love to cover your wedding reception...",
    "proposed_rate": 12000.00
  }'

# 3. View all my applications (unified inbox)
curl http://localhost:8000/api/v1/applications/ \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 4. Filter by status
curl "http://localhost:8000/api/v1/applications/?app_status=accepted" \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 5. Filter by type
curl "http://localhost:8000/api/v1/applications/?app_type=event" \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# 6. Withdraw a pending application
curl -X DELETE http://localhost:8000/api/v1/applications/<APP_ID> \
  -H "Authorization: Bearer <INFLUENCER_TOKEN>"

# ERROR CASES:
# Apply to closed campaign → 400: "This campaign is not accepting applications"
# Duplicate apply         → 400: "You have already applied to this campaign."
# Below min_followers     → 400: "This campaign requires at least 10,000 followers."
# Non-owner decides       → 403: "Only the brand that created this campaign can decide applications."
# Withdraw non-pending    → 400: "Only PENDING applications can be withdrawn."
"""
