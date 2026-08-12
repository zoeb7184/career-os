"""
backend/tests/test_health.py
─────────────────────────────
Tests for the master /health endpoint.
This is the most important test — if health breaks, everything is blind.

Run: make test-node N=tests  OR  pytest backend/tests/test_health.py -v
"""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    """Health endpoint must always return 200, even if nodes are degraded."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape():
    """Response must have 'overall' and 'nodes' keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert "overall" in data
    assert "nodes" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_all_expected_nodes_present():
    """Every node must be represented — catches typos in node names."""
    expected_nodes = {
        "postgres", "redis", "qdrant",
        "data_adzuna", "data_reed", "data_remotive",
        "etl_dedup", "etl_skills",
        "skill_extractor", "ats_analyzer",
        "recommender", "rag_advisor", "forecaster",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    nodes = set(response.json()["nodes"].keys())
    assert expected_nodes == nodes, f"Missing nodes: {expected_nodes - nodes}"


@pytest.mark.asyncio
async def test_health_not_started_nodes_dont_cause_overall_error():
    """
    not_started nodes should NOT make overall = 'error'.
    Only real errors should do that.
    """
    with (
        patch("app.api.health._check_postgres", return_value={"status": "ok", "detail": "ok"}),
        patch("app.api.health._check_redis",    return_value={"status": "ok", "detail": "ok"}),
        patch("app.api.health._check_qdrant",   return_value={"status": "ok", "detail": "ok"}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.json()["overall"] == "ok"


@pytest.mark.asyncio
async def test_health_overall_error_when_postgres_down():
    """overall must be 'error' if postgres is down."""
    with patch("app.api.health._check_postgres", return_value={"status": "error", "detail": "connection refused"}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.json()["overall"] == "error"


@pytest.mark.asyncio
async def test_root_endpoint():
    """Root / must return app name and links."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Career OS API"
    assert "/health" in data["health"]
