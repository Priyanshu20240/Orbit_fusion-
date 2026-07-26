"""M4 — cloud masking op-graph."""
import ee

from app.services.fusion.masking import CSPLUS_ID, mask_landsat, mask_s2


def test_mask_s2_uses_scl_and_cloud_score_plus():
    out = mask_s2(ee.Image("S2"))
    names = out.op_names()
    assert "updateMask" in names
    # cs_cdf is selected (Cloud Score+), and SCL is selected
    selects = [o["args"][0] for o in out.find("select")]
    assert "SCL" in selects
    assert "cs_cdf" in selects


def test_mask_landsat_uses_qa_pixel_bitmask():
    out = mask_landsat(ee.Image("L8"))
    names = out.op_names()
    assert "bitwiseAnd" in names
    assert "updateMask" in names
    assert out.find("select")[0]["args"][0] == "QA_PIXEL"


def test_csplus_id_constant():
    assert "CLOUD_SCORE_PLUS" in CSPLUS_ID
