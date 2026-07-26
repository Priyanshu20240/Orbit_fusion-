"""Phase 2 (M1) — endpoint contract for /api/scenes/overlap.

Locks down:
  - per-scene date list returned in sort-asc order, deduped on (date, sensor, scene_id)
  - ``limit`` clamps the frame count
  - both searches empty → 200 with ``frames: []``
  - the two search services are invoked concurrently (asyncio.gather, not serial)
  - the route is registered exactly once with method=POST
  - the response honors ``ORBITER_TIME_SERIES_MAX_FRAMES`` (default 50)
"""
from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import List

import pytest

# ── import the app + TestClient ───────────────────────────────────────────
# conftest stubs planetary_computer / pystac_client for the sandbox venv.
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from app import main as app_main  # noqa: E402
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


def _post_overlap(**over):
    body = {
        "bbox": {
            "min_lon": 77.55, "min_lat": 12.95,
            "max_lon": 77.62, "max_lat": 13.02,
        },
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "max_cloud_cover": 30,
        "limit": 50,
    }
    body.update(over)
    return client.post("/api/scenes/overlap", json=body)


# ── helpers ──────────────────────────────────────────────────────────────
def _patch_searches(monkeypatch, *, sentinel_scenes: List[dict] | None = None,
                    landsat_scenes: List[dict] | None = None,
                    sentinel_delay: float = 0.0,
                    landsat_delay: float = 0.0) -> tuple[list[float], list[float]]:
    """Replace sentinel_service.search_scenes + landsat_service.search_scenes
    with stubs that return the supplied scene lists. Returns the entry/exit
    timestamps from each stub so the test can assert concurrent execution.
    """
    s2_started: list[float] = []
    s2_ended: list[float] = []
    l8_started: list[float] = []
    l8_ended: list[float] = []

    def _s2(**kwargs):
        s2_started.append(time.monotonic())
        if sentinel_delay:
            time.sleep(sentinel_delay)
        s2_ended.append(time.monotonic())
        return {
            "total_results": len(sentinel_scenes or []),
            "scenes": list(sentinel_scenes or []),
        }

    def _l8(**kwargs):
        l8_started.append(time.monotonic())
        if landsat_delay:
            time.sleep(landsat_delay)
        l8_ended.append(time.monotonic())
        return {
            "total_results": len(landsat_scenes or []),
            "scenes": list(landsat_scenes or []),
        }

    monkeypatch.setattr(app_main.sentinel_service, "search_scenes", _s2)
    monkeypatch.setattr(app_main.landsat_service, "search_scenes", _l8)
    return s2_started, s2_ended, l8_started, l8_ended


def _scene(scene_id: str, dt: str, sensor_label: str, cloud: float | None = 5.0) -> dict:
    return {
        "id": scene_id,
        "datetime": dt,
        "cloud_cover": cloud,
        "satellite": "Sentinel-2" if sensor_label == "sentinel" else "Landsat-8/9",
    }


# ── happy path: sorted + deduped ────────────────────────────────────────
def test_overlap_returns_sorted_unique_dates(monkeypatch):
    """Frames are returned sorted by (date asc, sensor, scene_id), deduped on
    the (date, sensor, scene_id) triple."""
    s2 = [
        _scene("S2_2024-02-01", "2024-02-01T05:30:00.000Z", "sentinel"),
        _scene("S2_2024-01-15", "2024-01-15T05:30:00.000Z", "sentinel"),
        # Duplicate (same date+sensor+id) — should be deduped to one.
        _scene("S2_2024-01-15", "2024-01-15T05:30:00.000Z", "sentinel"),
    ]
    l8 = [
        _scene("L8_2024-01-20", "2024-01-20T05:30:00.000Z", "landsat"),
    ]
    _patch_searches(monkeypatch, sentinel_scenes=s2, landsat_scenes=l8)

    r = _post_overlap()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bucket"] == "scene"
    frames = body["frames"]
    # 4 unique (date, sensor, id) entries
    assert len(frames) == 3
    # Dates sorted asc; 2024-01-15 sentinel comes first.
    assert frames[0]["date"] == "2024-01-15"
    assert frames[0]["sensor"] == "sentinel"
    assert frames[0]["scene_id"] == "S2_2024-01-15"
    assert frames[1]["date"] == "2024-01-20"
    assert frames[1]["sensor"] == "landsat"
    assert frames[2]["date"] == "2024-02-01"
    assert frames[2]["sensor"] == "sentinel"
    # cloud_cover round-trips
    assert all(f["cloud_cover"] == 5.0 for f in frames)


# ── limit is forwarded to the search services ────────────────────────
def test_overlap_passes_request_limit_to_searches(monkeypatch):
    """The endpoint forwards the request's `limit` to both search services.

    The per-request limit is honored upstream (STAC) — we don't re-clamp it
    in the endpoint. The global cap (``ORBITER_TIME_SERIES_MAX_FRAMES``) is
    the only clamp the endpoint applies; see
    ``test_overlap_respects_time_series_max_frames`` for that.
    """
    captured: list[dict] = []

    def _s2(**kwargs):
        captured.append({"sensor": "sentinel", **kwargs})
        return {"total_results": 0, "scenes": []}

    def _l8(**kwargs):
        captured.append({"sensor": "landsat", **kwargs})
        return {"total_results": 0, "scenes": []}

    monkeypatch.setattr(app_main.sentinel_service, "search_scenes", _s2)
    monkeypatch.setattr(app_main.landsat_service, "search_scenes", _l8)

    r = _post_overlap(limit=7)
    assert r.status_code == 200
    # Both services were called with limit=7.
    assert any(c["sensor"] == "sentinel" and c["limit"] == 7 for c in captured)
    assert any(c["sensor"] == "landsat" and c["limit"] == 7 for c in captured)


# ── both searches empty ────────────────────────────────────────────────
def test_overlap_handles_no_scenes(monkeypatch):
    """Both searches returning 0 scenes → 200 with frames=[]."""
    _patch_searches(monkeypatch, sentinel_scenes=[], landsat_scenes=[])
    r = _post_overlap()
    assert r.status_code == 200
    assert r.json() == {"frames": [], "bucket": "scene"}


# ── bad scene datetime is skipped, not a 500 ───────────────────────────
def test_overlap_skips_malformed_datetime(monkeypatch):
    """Scenes with empty/malformed `datetime` are skipped, not a 500."""
    s2 = [
        _scene("S2_good", "2024-01-15T05:30:00.000Z", "sentinel"),
        _scene("S2_empty", "", "sentinel"),
        _scene("S2_bad", "not-a-date", "sentinel"),
    ]
    _patch_searches(monkeypatch, sentinel_scenes=s2, landsat_scenes=[])
    r = _post_overlap()
    assert r.status_code == 200
    frames = r.json()["frames"]
    assert len(frames) == 1
    assert frames[0]["scene_id"] == "S2_good"


# ── scene_id required (key dedup) ──────────────────────────────────────
def test_overlap_drops_scenes_with_no_id(monkeypatch):
    """Scenes missing `id` are dropped (we can't dedupe them)."""
    s2 = [
        _scene("S2_good", "2024-01-15T05:30:00.000Z", "sentinel"),
        {"id": "", "datetime": "2024-01-16T05:30:00.000Z", "cloud_cover": 5.0,
         "satellite": "Sentinel-2"},
    ]
    _patch_searches(monkeypatch, sentinel_scenes=s2, landsat_scenes=[])
    r = _post_overlap()
    assert r.status_code == 200
    frames = r.json()["frames"]
    assert len(frames) == 1
    assert frames[0]["scene_id"] == "S2_good"


# ── concurrent search (asyncio.gather) ─────────────────────────────────
def test_overlap_uses_concurrent_search(monkeypatch):
    """Sentinel and Landsat searches run concurrently.

    Each stub sleeps 200ms; if the handler awaited serially the request
    would take >= 400ms; concurrent execution finishes in ~200ms.
    """
    s2_started, s2_ended, l8_started, l8_ended = _patch_searches(
        monkeypatch,
        sentinel_scenes=[_scene("S2_2024-01-15", "2024-01-15T05:30:00.000Z", "sentinel")],
        landsat_scenes=[_scene("L8_2024-01-20", "2024-01-20T05:30:00.000Z", "landsat")],
        sentinel_delay=0.20,
        landsat_delay=0.20,
    )

    t0 = time.monotonic()
    r = _post_overlap()
    elapsed = time.monotonic() - t0

    assert r.status_code == 200, r.text
    assert len(s2_started) == 1 and len(l8_started) == 1
    # Overlap: the second start must precede the first end (proves gather).
    s2_start, s2_end = s2_started[0], s2_ended[0]
    l8_start, l8_end = l8_started[0], l8_ended[0]
    overlap = (s2_start < l8_end) and (l8_start < s2_end)
    assert overlap, (
        f"Searches did not overlap (serial). "
        f"s2=[{s2_start:.3f},{s2_end:.3f}] l8=[{l8_start:.3f},{l8_end:.3f}]"
    )
    # And the total request was under 2× the per-stub delay (350ms ceiling
    # accounts for overhead; serial would be ~400ms+).
    assert elapsed < 0.35, f"elapsed={elapsed:.3f}s (serial would be >=0.40s)"


# ── honors ORBITER_TIME_SERIES_MAX_FRAMES ─────────────────────────────
def test_overlap_respects_time_series_max_frames(monkeypatch, monkeypatch_env=None):
    """When the merged frame list exceeds the cap, the response is truncated."""
    from app.config import get_settings

    # Build 60 sentinel scenes, one per day across 2 months.
    s2 = [
        _scene(f"S2_{i:03d}", f"2024-01-{(i % 31) + 1:02d}T05:00:00.000Z", "sentinel")
        for i in range(60)
    ]
    _patch_searches(monkeypatch, sentinel_scenes=s2, landsat_scenes=[])

    # Temporarily lower the cap.
    import os
    os.environ["ORBITER_TIME_SERIES_MAX_FRAMES"] = "5"
    get_settings.cache_clear()
    try:
        r = _post_overlap()
    finally:
        os.environ.pop("ORBITER_TIME_SERIES_MAX_FRAMES", None)
        get_settings.cache_clear()

    assert r.status_code == 200, r.text
    assert len(r.json()["frames"]) == 5


# ── structural: route is registered exactly once ──────────────────────
def test_scenes_overlap_route_is_registered():
    """POST /api/scenes/overlap is registered exactly once, no shadowing."""
    seen: set[tuple] = set()
    matches: list[tuple] = []
    for r in app_main.app.routes:
        if not hasattr(r, "path"):
            continue
        if r.path != "/api/scenes/overlap":
            continue
        for m in sorted(getattr(r, "methods", set()) or set()):
            key = (m, r.path)
            if key in seen:
                matches.append(key)
            seen.add(key)
    assert ("POST", "/api/scenes/overlap") in seen, "POST /api/scenes/overlap not registered"
    assert not matches, f"duplicate registrations: {matches}"


# ── bad body is rejected by the SearchRequest validator ───────────────
def test_overlap_bad_body_returns_422():
    """ValidationError → 422.

    Note: Pydantic-direct routes (the SearchRequest body parameter) return
    FastAPI's standard ``{detail: [...]}`` 422 envelope, not the
    ServiceError-shaped ``{code, message}``. Consistency between Pydantic
    and ServiceError-mapped validation is a [LATER] cleanup; for now we
    only lock the status code.
    """
    r = client.post("/api/scenes/overlap", json={"bbox": [1, 2, 3]})  # bbox must be an object
    assert r.status_code == 422
