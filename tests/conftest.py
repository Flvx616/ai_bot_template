"""Pytest configuration and shared fixtures.

Tests run without real services — all external connections are mocked.
"""

import contextlib
import os
import sys
import typing as tp
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Set env vars BEFORE any imports to satisfy Pydantic validators
os.environ.setdefault("LOG_PATH", os.getcwd())
os.environ.setdefault("METRIC_PATH", os.getcwd())
os.environ.setdefault("AUDIT_LOG_PATH", os.getcwd())
os.environ.setdefault("OPENAI_API_KEY", "test-key-0000")
os.environ.setdefault("OPENAI_FOLDER_ID", "b1g_test_folder")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-lf-test")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
os.environ.setdefault("PG_PASSWORD", "test")

# Add src/ to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@contextlib.asynccontextmanager
async def _noop_lifespan(_) -> tp.AsyncContextManager:
    """No-op lifespan — skips all service connections during tests."""
    yield


@pytest.fixture(scope="session")
def app():
    """FastAPI app instance with mocked startup/shutdown lifecycle."""
    with patch("service.api.lifespan", _noop_lifespan):
        from service.api import create_app
        return create_app()


@pytest.fixture(scope="session")
def client(app):
    """HTTP test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
