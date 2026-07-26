"""M5 — build_fusion_map composes the M4 blocks into the getMapId contract."""
from datetime import date

import ee
import pytest

from app.models.schemas import FusionRequest
from app.services.fusion.registry import NoImageryError
from app.services.gee_fusion_service import gee_fusion_service


def _req(**over):
    base = dict(
        bounds=[77.55, 12.95, 77.62, 13.02],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
    )
    base.update(over)
    return FusionRequest(**base)


def test_build_fusion_map_shape():
    ee.set_collection_size(4)
    try:
        out = gee_fusion_service.build_fusion_map(_req(visualization="ndvi"))
    finally:
        ee.reset()
    assert "{z}/{x}/{y}" in out["tile_url_template"]
    assert out["scene_counts"] == {"sentinel": 4, "landsat": 4}
    assert out["visualization"] == "ndvi"
    assert out["bounds"] == [[12.95, 77.55], [13.02, 77.62]]  # [[S,W],[N,E]]
    assert out["max_native_zoom"] == 14
    assert out["mapid"]


def test_no_imagery_raises():
    ee.set_collection_size(0)
    try:
        with pytest.raises(NoImageryError):
            gee_fusion_service.build_fusion_map(_req())
    finally:
        ee.reset()


def test_lst_sentinel_only_raises_value_error():
    ee.set_collection_size(3)
    try:
        with pytest.raises(ValueError):
            gee_fusion_service.build_fusion_map(
                _req(visualization="lst", platforms=["sentinel"])
            )
    finally:
        ee.reset()


def test_timelapse_frame_helper_uses_registry():
    from app.services.gee_fusion_service import _visualize_frame

    frame = _visualize_frame(ee.Image("L8"), "landsat", "ndvi")
    names = frame.op_names()
    assert "updateMask" in names          # masked
    assert "normalizedDifference" in names  # index via registry
    assert "visualize" in names           # rendered for the GIF
