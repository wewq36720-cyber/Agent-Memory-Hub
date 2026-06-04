"""Smoke checks for /health and unknown route 404."""
from __future__ import annotations


def test_health_basic(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_health_db(api_client):
    r = api_client.get("/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body.get("db") == "connected"


def test_unknown_endpoint_404(api_client):
    r = api_client.get("/api/v1/nonexistent")
    assert r.status_code == 404
