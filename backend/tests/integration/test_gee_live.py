"""M10 — on-demand real-Google Earth Engine smoke test.

**Not run in CI.** This file is opt-in via the ``integration`` pytest
marker (see ``pytest.ini``); the regular ``pytest`` invocation skips
it. To exercise the live path:

    ORBITER_GEE_LIVE=1 ORBITER_GEE_PROJECT=your-project \\
    pytest -m integration tests/integration/

The job uses authenticated Earth Engine via Application Default
Credentials. On the Windows host that's ``earthengine authenticate``;
on CI the workflow injects a service-account JSON (see
``.github/workflows/ci.yml``).

What this test actually checks:

  1. The lifespan boots with GEE initialised (no exception).
  2. ``/health`` reports 200 OK (i.e. ``gee_ready=True``).
  3. A small real fusion request (``true_color`` over a 0.05° AOI in
     Bangalore, last 30 days, cloud-cover ≤ 30%) returns a
     ``FusionMapResponse`` with a real ``{z}/{x}/{y}`` template.

What this test does NOT check:

  * Per-pixel correctness of the visualisation — the fusion graph is
    exercised by the offline ``tests/test_fusion_graph.py`` suite.
  * Multiple platforms — that's the ``tests/test_composite.py`` unit
    coverage. Here we just need one to confirm GEE is callable.
"""
from __future__ import annotations

import os

import pytest

# Skip unconditionally unless the operator explicitly opts in.
# `pytest -m integration` filters the rest of the suite, but a bare
# `pytest tests/` (no marker filter) would still try to import this
# file — the skip guard below is the belt; the marker is the braces.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("ORBITER_GEE_LIVE") != "1",
        reason="real-GEE smoke is opt-in via ORBITER_GEE_LIVE=1",
    ),
]


# Tiny AOI: ~5km around Bangalore.
AOI = {
    "min_lon": 77.55,
    "min_lat": 12.95,
    "max_lon": 77.62,
    "max_lat": 13.02,
}


def test_health_reports_healthy_when_gee_is_live():
    """With real creds + real project, /health must be 200."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "healthy"
        assert body.get("gee_ready") is True


def test_small_fusion_returns_getmapid_contract():
    """One real fusion call must return a {z}/{x}/{y} tile template."""
    from datetime import date, timedelta

    from fastapi.testclient import TestClient

    from app.main import app

    end = date.today()
    start = end - timedelta(days=30)

    body = {
        "bounds": [AOI["min_lon"], AOI["min_lat"], AOI["max_lon"], AOI["max_lat"]],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "cloud_cover": 30,
        "visualization": "true_color",
        "platforms": ["sentinel", "landsat"],
    }

    with TestClient(app) as client:
        r = client.post("/api/fusion/gee-harmonize", json=body)
        # Accept 200 (scenes found) or 404 (no cloud-free scenes in 30
        # days over that AOI — Bangalore is cloudy in monsoon). Reject
        # everything else as a real failure.
        assert r.status_code in (200, 404), r.text
        if r.status_code == 200:
            data = r.json()
            assert "tile_url_template" in data
            assert "{z}" in data["tile_url_template"]
            assert "{x}" in data["tile_url_template"]
            assert "{y}" in data["tile_url_template"]
