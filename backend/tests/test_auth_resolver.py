"""M2 — GEE auth resolver + lifespan state + auth-free import."""
import inspect
import sys
from types import SimpleNamespace

from app.services import gee_auth


def _cfg(**over):
    base = dict(
        gee_project="test-project",
        gee_service_account_json=None,
        gee_service_account_file=None,
        gee_high_volume=True,
    )
    base.update(over)
    return SimpleNamespace(**base)


# ── regression guard: no hardcoded project anywhere in the resolver ──
def test_no_hardcoded_project():
    assert "compact-arc-482620-r8" not in inspect.getsource(gee_auth)


# ── resolver priority + endpoint toggle ──
def test_adc_default_path():
    import ee

    ee.reset()
    gee_auth.init_earth_engine(_cfg())
    assert len(ee.initialize_calls) == 1
    kw = ee.initialize_calls[0]["kwargs"]
    assert kw.get("project") == "test-project"
    assert kw.get("opt_url") == "https://earthengine-highvolume.googleapis.com"
    assert "credentials" not in kw  # ADC path, no SA creds


def test_high_volume_toggle_off():
    import ee

    ee.reset()
    gee_auth.init_earth_engine(_cfg(gee_high_volume=False))
    assert ee.initialize_calls[0]["kwargs"].get("opt_url") is None


def test_service_account_json_wins_over_file():
    import ee

    ee.reset()
    sa = '{"client_email": "svc@proj.iam.gserviceaccount.com", "private_key": "x"}'
    gee_auth.init_earth_engine(
        _cfg(gee_service_account_json=sa, gee_service_account_file="/ignored.json")
    )
    assert "credentials" in ee.initialize_calls[0]["kwargs"]


def test_service_account_file_path():
    import ee

    ee.reset()
    gee_auth.init_earth_engine(_cfg(gee_service_account_file="/keys/ee-sa.json"))
    assert "credentials" in ee.initialize_calls[0]["kwargs"]


# ── the headline guarantee: importing the service authenticates nothing ──
def test_service_import_is_auth_free():
    import ee

    ee.reset()
    sys.modules.pop("services.gee_fusion_service", None)
    import app.services.gee_fusion_service  # noqa: F401

    assert ee.initialize_calls == [], "importing the service must not call ee.Initialize"


# ── lifespan degradation contract ──
def test_configure_gee_state_ok(monkeypatch):
    monkeypatch.setattr(gee_auth, "init_earth_engine", lambda cfg: None)
    st = SimpleNamespace()
    gee_auth.configure_gee_state(st, _cfg())
    assert st.gee_ready is True
    assert st.gee_error is None


def test_configure_gee_state_degrades(monkeypatch):
    def boom(cfg):
        raise RuntimeError("no creds")

    monkeypatch.setattr(gee_auth, "init_earth_engine", boom)
    st = SimpleNamespace()
    gee_auth.configure_gee_state(st, _cfg())
    assert st.gee_ready is False
    assert st.gee_error is not None
