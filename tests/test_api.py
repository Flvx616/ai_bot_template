"""Basic API endpoint tests.

These tests verify route structure and input validation.
No real services are required — startup is mocked in conftest.py.

Run:
    make test
    # or:
    uv run pytest tests/ -v
"""

VALID_HEADERS = {
    "x-trace-id": "550e8400-e29b-41d4-a716-446655440000",
    "x-request-time": "2025-01-01T12:00:00Z",
    "x-source-name": "pytest",
    "x-user-id": "test-user-001",
}


# ── /health ─────────────────────────────────────────────────────────────────

def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_has_status(client):
    data = client.get("/health").json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")


def test_health_response_has_services(client):
    data = client.get("/health").json()
    assert "services" in data
    assert isinstance(data["services"], dict)
    for key in ("postgres", "redis", "chromadb", "langfuse"):
        assert key in data["services"]


# ── /info ────────────────────────────────────────────────────────────────────

def test_info_returns_200_or_500(client):
    # 200 when package is installed (uv sync), 500 otherwise
    response = client.get("/info")
    assert response.status_code in (200, 500)


def test_info_response_structure(client):
    response = client.get("/info")
    if response.status_code == 200:
        data = response.json()
        assert "name" in data
        assert "version" in data


# ── /like, /dislike ──────────────────────────────────────────────────────────

def test_like_returns_200(client):
    assert client.get("/like").status_code == 200


def test_dislike_returns_200(client):
    assert client.get("/dislike").status_code == 200


# ── /api/v1/chat — validation ────────────────────────────────────────────────

def test_chat_missing_headers_returns_422(client):
    response = client.post("/api/v1/chat", json={"text": "Hello world"})
    assert response.status_code == 422


def test_chat_text_too_short_returns_422(client):
    response = client.post(
        "/api/v1/chat",
        headers=VALID_HEADERS,
        json={"text": "Hi"},  # min_length=4
    )
    assert response.status_code == 422


def test_chat_text_too_long_returns_422(client):
    response = client.post(
        "/api/v1/chat",
        headers=VALID_HEADERS,
        json={"text": "x" * 513},  # max_length=512
    )
    assert response.status_code == 422


def test_chat_valid_request_accepted(client):
    """Valid request should not fail on validation (may fail on business logic without services)."""
    response = client.post(
        "/api/v1/chat",
        headers=VALID_HEADERS,
        json={"text": "What can you help me with?", "context": ""},
    )
    # 200 (if mocked) or 500 (service not available) — not 422
    assert response.status_code != 422


# ── /api/v1/test_invoke — validation ─────────────────────────────────────────

def test_test_invoke_missing_headers_returns_422(client):
    response = client.post("/api/v1/test_invoke", json={"question": "Who are you?"})
    assert response.status_code == 422


def test_test_invoke_valid_request_accepted(client):
    response = client.post(
        "/api/v1/test_invoke",
        headers=VALID_HEADERS,
        json={"question": "Who are you?"},
    )
    assert response.status_code != 422
