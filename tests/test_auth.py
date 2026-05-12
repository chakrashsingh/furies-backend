"""
tests/test_auth.py
───────────────────
Sample test cases for the auth system.
Run with: pytest tests/ -v

These show the expected request/response shapes — useful as live documentation.
"""

# ── Manual curl/httpx test scripts (run against a live server) ─────────────

SIGNUP_REQUEST = {
    "description": "POST /api/v1/auth/signup",
    "body": {
        "full_name": "Riya Sharma",
        "email": "riya@example.com",
        "password": "Str0ngPass1",
        "role": "influencer"
    },
    "expected_status": 201,
    "expected_fields": ["id", "email", "full_name", "role", "is_active", "created_at"],
}

LOGIN_REQUEST = {
    "description": "POST /api/v1/auth/login",
    "body": {
        "email": "riya@example.com",
        "password": "Str0ngPass1"
    },
    "expected_status": 200,
    "expected_fields": ["access_token", "token_type", "expires_in", "user"],
}

ME_REQUEST = {
    "description": "GET /api/v1/auth/me",
    "headers": {"Authorization": "Bearer <token_from_login>"},
    "expected_status": 200,
}

WRONG_PASSWORD = {
    "description": "POST /api/v1/auth/login — wrong password",
    "body": {"email": "riya@example.com", "password": "WrongPass1"},
    "expected_status": 401,
}

DUPLICATE_EMAIL = {
    "description": "POST /api/v1/auth/signup — duplicate email",
    "body": {
        "full_name": "Someone Else",
        "email": "riya@example.com",
        "password": "Str0ngPass1",
        "role": "brand"
    },
    "expected_status": 409,
}

# ── Unit test: password validation ────────────────────────────────────────────
def test_password_hashing():
    from app.core.security import hash_password, verify_password
    pw = "MyPass123"
    h  = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h)
    assert not verify_password("WrongPass", h)

def test_jwt_roundtrip():
    from app.core.security import create_access_token, decode_access_token
    import uuid
    uid = str(uuid.uuid4())
    token = create_access_token(subject=uid, role="influencer")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == uid
    assert payload["role"] == "influencer"

def test_schema_password_validation():
    from pydantic import ValidationError
    from app.schemas.user import UserCreate
    try:
        UserCreate(full_name="Test", email="t@t.com", password="nodigits", role="user")
        assert False, "Should have raised"
    except ValidationError:
        pass  # expected
