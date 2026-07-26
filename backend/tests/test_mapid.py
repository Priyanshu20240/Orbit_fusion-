"""M4 — mint_mapid produces an XYZ template; VisSpec translation is correct."""
import ee

from app.services.fusion.mapid import mint_mapid, visspec_to_vis
from app.services.fusion.registry import VisSpec


def test_mint_returns_xyz_template():
    out = mint_mapid(ee.Image("X"), VisSpec(bands=["ndvi"], min=-1, max=1, palette=["#000", "#fff"]))
    assert "{z}/{x}/{y}" in out["tile_url_template"]
    assert out["mapid"]


def test_visspec_translation_index():
    vis = visspec_to_vis(VisSpec(bands=["ndvi"], min=-0.2, max=0.8, palette=["#000", "#fff"]))
    assert vis["bands"] == ["ndvi"]
    assert vis["min"] == -0.2 and vis["max"] == 0.8
    assert vis["palette"] == ["#000", "#fff"]


def test_visspec_translation_rgb_gamma():
    vis = visspec_to_vis(VisSpec(bands=["red", "green", "blue"], min=0.0, max=0.3, gamma=1.1))
    assert vis["gamma"] == 1.1
    assert "palette" not in vis  # RGB has no palette


def test_getmapid_is_called():
    img = ee.Image("X")
    mint_mapid(img, VisSpec(bands=["ndvi"], min=0, max=1))
    assert "getMapId" in img.op_names()
