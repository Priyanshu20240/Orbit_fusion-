"""M4 — bounded composite ordering: mask < narrow-select < reduce."""
import ee

from app.services.fusion import composite as C


def _geom():
    return ee.Geometry.Rectangle([77.55, 12.95, 77.62, 13.02])


def test_s2_masks_before_narrow_before_median():
    coll = C.s2_collection(_geom(), "2024-01-01", "2024-03-31", 20, 25)
    img = C.composite(coll, "median")
    names = img.op_names()
    upd = [i for i, n in enumerate(names) if n == "updateMask"]
    sel = [i for i, n in enumerate(names) if n == "select"]
    med = names.index("median")
    assert upd, "expected a cloud mask (updateMask) in the graph"
    assert max(upd) < max(sel) < med, "mask must precede band-narrow which must precede reduce"


def test_limit_bounds_the_collection():
    coll = C.s2_collection(_geom(), "2024-01-01", "2024-03-31", 20, 25)
    assert "limit" in coll.op_names()


def test_no_reproject_or_samplerectangle():
    coll = C.landsat_collection(_geom(), "2024-01-01", "2024-03-31", 20, 25)
    img = C.composite(coll, "median")
    names = img.op_names()
    assert "reproject" not in names
    assert "sampleRectangle" not in names


def test_scene_count_uses_size_getinfo():
    ee.set_collection_size(7)
    try:
        coll = C.s2_collection(_geom(), "2024-01-01", "2024-03-31", 20, 25)
        assert C.scene_count(coll) == 7
    finally:
        ee.reset()
