# tests/test_dashboard.py
"""Tests for dashboard auth and routes."""

import os
import pytest

# Skip all tests if fastapi is not installed
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from pgql.dashboard.auth import get_dashboard_key


@pytest.fixture(autouse=True)
def reset_dashboard_key(monkeypatch):
    """Reset the dashboard key module state."""
    import pgql.dashboard.auth as auth_mod
    auth_mod._dashboard_key = None
    monkeypatch.setenv("DASHBOARD_API_KEY", "test-secret-key-123")
    yield


@pytest.fixture
def client():
    """Create a test client for the dashboard app."""
    from pgql.dashboard.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-Dashboard-Key": "test-secret-key-123"}


class TestDashboardAuth:
    """Test authentication on dashboard routes."""

    def test_static_root_no_auth(self, client):
        """Root page should be accessible without auth."""
        res = client.get("/")
        assert res.status_code == 200

    def test_api_health_no_auth_required(self, client):
        """Health endpoint should be accessible without auth (for Docker health checks)."""
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_api_health_with_valid_key(self, client, auth_headers):
        """API endpoints should work with valid key."""
        res = client.get("/api/health", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"

    def test_api_health_ignores_invalid_key(self, client):
        """Health endpoint ignores invalid key (auth exempt)."""
        res = client.get("/api/health", headers={"X-Dashboard-Key": "wrong-key"})
        assert res.status_code == 200

    def test_api_metrics_requires_auth(self, client):
        res = client.get("/api/metrics")
        assert res.status_code == 401

    def test_api_metrics_with_auth(self, client, auth_headers):
        res = client.get("/api/metrics", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_requests" in data

    def test_api_config_requires_auth(self, client):
        res = client.get("/api/config")
        assert res.status_code == 401

    def test_api_config_with_auth(self, client, auth_headers):
        res = client.get("/api/config", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "configured" in data


class TestDashboardHealthRoutes:
    """Test health check endpoints."""

    def test_health_response_format(self, client, auth_headers):
        res = client.get("/api/health", headers=auth_headers)
        data = res.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "version" in data

    def test_health_has_uptime(self, client, auth_headers):
        res = client.get("/api/health", headers=auth_headers)
        data = res.json()
        assert data["uptime_seconds"] >= 0


class TestDashboardMetricsRoutes:
    """Test metrics endpoints."""

    def test_metrics_summary(self, client, auth_headers):
        res = client.get("/api/metrics", headers=auth_headers)
        data = res.json()
        assert data["total_requests"] >= 0
        assert "success_rate" in data
        assert "tools" in data

    def test_metrics_requests_history(self, client, auth_headers):
        res = client.get("/api/metrics/requests?limit=5", headers=auth_headers)
        data = res.json()
        assert "requests" in data

    def test_metrics_errors(self, client, auth_headers):
        res = client.get("/api/metrics/errors?limit=5", headers=auth_headers)
        data = res.json()
        assert "errors" in data


class TestDashboardConfigRoutes:
    """Test config endpoints."""

    def test_get_config(self, client, auth_headers):
        res = client.get("/api/config", headers=auth_headers)
        data = res.json()
        assert "configured" in data
        assert "config" in data

    def test_list_api_keys(self, client, auth_headers):
        res = client.get("/api/config/keys", headers=auth_headers)
        data = res.json()
        assert "keys" in data
        assert "count" in data

    def test_get_rate_limit(self, client, auth_headers):
        res = client.get("/api/config/rate-limit", headers=auth_headers)
        data = res.json()
        assert "rate" in data
        assert "per_seconds" in data

    def test_get_cache_stats(self, client, auth_headers):
        res = client.get("/api/config/cache", headers=auth_headers)
        assert res.status_code == 200

    def test_clear_cache(self, client, auth_headers):
        res = client.post("/api/config/cache/clear", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
