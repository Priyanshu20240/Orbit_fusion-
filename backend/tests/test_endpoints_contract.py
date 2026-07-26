"""M7 — endpoint contract.

Locks down:
  - /api/fusion/gee-harmonize returns the FusionMapResponse shape
    ({z}/{x}/{y} template, bounds [[S,W],[N,E]], expires_at, max_native_zoom,
     scene_counts, visualization).
  - /health returns 200 healthy when gee_ready=True and 503 degraded when False.
  - /api/fusion/{fusion_id}/refresh-mapid round-trips a fresh tile template
    (404 when fusion_id is unknown).
  - Exactly one CORS middleware.
  - All routes have unique (path, method) pairs.
  - No orphaned FusionProcessing* / old-HealthResponse references in main.py.
  - Phase 1 (M4): the 3 new strategies (gap_fill, harmonized_l8, real_lst)
    are reachable through the same endpoint.
"""
from __future__ import annotations

import inspect
from datetime import date

import pytest


# ── import the app + TestClient ───────────────────────────────────────────
# conftest stubs planetary_computer / pystac_client for the sandbox venv.
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from app import main as app_main  # noqa: E402
from app.core import mapid_cache  # noqa: E402
from app.core.errors import ServiceError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app_main.app)


@pytest.fixture(autouse=True)
def _wire_ee_pool():
    """TestClient does NOT run the lifespan, so app.state.ee_pool is missing.
    Stand up a tiny one for the test (GEE is faked so no real work happens)."""
    pool = ThreadPoolExecutor(max_workers=2)
    app_main.app.state.ee_pool = pool
    app_main.app.state.gee_ready = True
    app_main.app.state.gee_error = None
    yield
    pool.shutdown(wait=False)


# ── helpers ──────────────────────────────────────────────────────────────
def _post_harmonize(**over):
    body = {
        "bounds": [77.55, 12.95, 77.62, 13.02],
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "cloud_cover": 20,
        "visualization": "true_color",
        "platforms": ["sentinel", "landsat"],
    }
    body.update(over)
    return client.post("/api/fusion/gee-harmonize", json=body)


def _force_gee_ready(value: bool):
    """Pretend GEE is (or isn't) initialized for the request."""
    app_main.app.state.gee_ready = value
    if not value:
        app_main.app.state.gee_error = "synthetic: not initialized"


# ── health ───────────────────────────────────────────────────────────────
def test_health_ready_returns_200():
    _force_gee_ready(True)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["gee_project"] == "test-project"
    assert body["gee_error"] is None


def test_health_not_ready_returns_503():
    _force_gee_ready(False)
    try:
        r = client.get("/health")
    finally:
        _force_gee_ready(True)
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["gee_error"] is not None


# ── gee-harmonize contract ───────────────────────────────────────────────
def test_gee_harmonize_returns_tile_template(monkeypatch):
    """When GEE is 'ready' and faked-ee returns scenes, response has the
    getMapId XYZ template + all required fields."""
    import ee  # fake_ee injected by conftest

    _force_gee_ready(True)
    ee.set_collection_size(4)
    try:
        r = _post_harmonize()
    finally:
        ee.reset()
    assert r.status_code == 200, r.text
    body = r.json()
    assert "{z}/{x}/{y}" in body["tile_url_template"]
    assert body["bounds"] == [[12.95, 77.55], [13.02, 77.62]]  # [[S,W],[N,E]]
    assert "expires_at" in body
    assert body["max_native_zoom"] == 14
    assert body["visualization"] == "true_color"
    assert body["scene_counts"] == {"sentinel": 4, "landsat": 4}
    assert body["mapid"]


def test_gee_harmonize_unavailable_returns_503():
    _force_gee_ready(False)
    try:
        r = _post_harmonize()
    finally:
        _force_gee_ready(True)
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "gee_unavailable"


def test_gee_harmonize_bad_body_returns_422():
    _force_gee_ready(True)
    # bounds wrong length (5 elements) — Pydantic conlist fires.
    r = client.post(
        "/api/fusion/gee-harmonize",
        json={
            "bounds": [1, 2, 3, 4, 5],
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "visualization": "true_color",
            "platforms": ["sentinel", "landsat"],
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"


def test_gee_harmonize_no_imagery_returns_404():
    """When faked-ee collection_size is 0 and platforms are both requested,
    NoImageryError is raised by build_fusion_map and the handler maps it
    to 404 no_imagery."""
    import ee

    _force_gee_ready(True)
    ee.set_collection_size(0)
    try:
        r = _post_harmonize()
    finally:
        ee.reset()
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "no_imagery"


# ── refresh-mapid ────────────────────────────────────────────────────────
def test_refresh_mapid_unknown_id_returns_404():
    _force_gee_ready(True)
    r = client.get("/api/fusion/does-not-exist/refresh-mapid")
    assert r.status_code == 404
    assert r.json()["code"] == "no_imagery"


def test_refresh_mapid_round_trip(monkeypatch):
    """Build a fusion first (populates the image+mapid cache), then refresh."""
    import ee

    _force_gee_ready(True)
    ee.set_collection_size(3)
    try:
        r1 = _post_harmonize()
    finally:
        ee.reset()
    assert r1.status_code == 200, r1.text
    fusion_id = r1.json()["fusion_id"]
    r2 = client.get(f"/api/fusion/{fusion_id}/refresh-mapid")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "{z}/{x}/{y}" in body["tile_url_template"]
    assert body["fusion_id"] == fusion_id
    assert body["max_native_zoom"] == 14


# ── structural guards ────────────────────────────────────────────────────
def test_exactly_one_cors_middleware():
    """M3's single-CORS invariant. Definitive guard: the only
    `add_middleware` registration in main.py must be CORS, and it must appear
    exactly once."""
    src = inspect.getsource(app_main)
    # add_middleware( must appear exactly once.
    add_mw_count = sum(
        1 for line in src.splitlines()
        if line.strip().startswith("app.add_middleware(")
    )
    assert add_mw_count == 1, f"add_middleware appears {add_mw_count} times"
    # And that one must be CORSMiddleware.
    assert "CORSMiddleware" in src
    # No wildcard origins — design C.1.7 calls this out.
    assert 'allow_origins=["*"]' not in src


def test_routes_unique():
    """No duplicate (path, method) pairs. Regression guard for the M5
    'duplicate /api/fusion/{id}/tiles' shadow-route bug."""
    seen = set()
    dupes = []
    for r in app_main.app.routes:
        if not hasattr(r, "path"):
            continue
        for m in sorted(getattr(r, "methods", set()) or set()):
            key = (m, r.path)
            if key in seen:
                dupes.append(key)
            seen.add(key)
    assert not dupes, f"duplicate (method, path): {dupes}"


def test_no_orphaned_schemas_in_main():
    src = inspect.getsource(app_main)
    # The doomed schema names must not appear anywhere in main.py.
    assert "FusionProcessingRequest" not in src
    assert "FusionProcessingResponse" not in src
    assert "HealthResponse" not in src  # the OLD HealthResponse, not the inline dict
    # And the doomed paths are gone.
    for doomed in (
        "/api/fusion/harmonize",  # the legacy STAC one
        "/api/fusion/process",
        "/api/tiles/",
        "/api/analysis/",
        "/api/export/",
        "/api/datasets/",
        "/api/fusion/gee/status",
    ):
        assert doomed not in src, f"doomed path {doomed!r} still in main.py"


# ────────────────────────────────────────────────────────────────────
# Phase 1 (M4): the 3 new strategies are reachable via the endpoint.
# ────────────────────────────────────────────────────────────────────

import ee  # noqa: E402  — conftest has injected the fake_ee module

_PHASE1_VIZ = (
    ("gap_fill",       ["sentinel", "landsat"]),
    ("harmonized_l8",  ["sentinel", "landsat"]),
    ("real_lst",       ["landsat"]),
)


@pytest.mark.parametrize("viz,platforms", _PHASE1_VIZ)
def test_phase1_modes_reachable_through_endpoint(viz, platforms):
    """Each Phase 1 mode returns a FusionMapResponse with a real tile template."""
    _force_gee_ready(True)
    ee.reset()
    ee.set_collection_size(3)
    try:
        r = _post_harmonize(visualization=viz, platforms=platforms)
    finally:
        ee.reset()
    assert r.status_code == 200, f"{viz}: {r.text}"
    body = r.json()
    assert body["visualization"] == viz
    assert "tile_url_template" in body
    assert "{z}" in body["tile_url_template"]
    assert "{x}" in body["tile_url_template"]
    assert "{y}" in body["tile_url_template"]
    assert body["max_native_zoom"] == 14
    assert "scene_counts" in body
    assert "expires_at" in body
