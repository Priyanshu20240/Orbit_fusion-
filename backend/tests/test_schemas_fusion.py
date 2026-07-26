"""M4 — additive fusion schemas validate correctly."""
import pytest
from pydantic import ValidationError

from app.models.schemas import FusionMapResponse, FusionRequest, SceneCounts


def test_valid_request_defaults():
    r = FusionRequest(bounds=[77.5, 12.9, 77.6, 13.0], start_date="2024-01-01", end_date="2024-05-01")
    assert r.visualization == "true_color"
    assert r.platforms == ["sentinel", "landsat"]
    assert r.cloud_cover == 20.0


def test_start_after_end_raises():
    with pytest.raises(ValidationError):
        FusionRequest(bounds=[1, 2, 3, 4], start_date="2024-05-01", end_date="2024-01-01")


def test_bad_visualization_raises():
    with pytest.raises(ValidationError):
        FusionRequest(bounds=[1, 2, 3, 4], start_date="2024-01-01", end_date="2024-05-01", visualization="bogus")


def test_short_bounds_raises():
    with pytest.raises(ValidationError):
        FusionRequest(bounds=[1, 2, 3], start_date="2024-01-01", end_date="2024-05-01")


def test_cloud_cover_out_of_range_raises():
    with pytest.raises(ValidationError):
        FusionRequest(bounds=[1, 2, 3, 4], start_date="2024-01-01", end_date="2024-05-01", cloud_cover=150)


def test_response_shape():
    resp = FusionMapResponse(
        fusion_id="abc",
        tile_url_template="https://x/{z}/{x}/{y}",
        bounds=[[12.9, 77.5], [13.0, 77.6]],
        visualization="ndvi",
        scene_counts=SceneCounts(sentinel=3, landsat=2),
        expires_at="2026-07-24T00:00:00Z",
    )
    assert resp.max_native_zoom == 14
    assert resp.scene_counts.sentinel == 3
