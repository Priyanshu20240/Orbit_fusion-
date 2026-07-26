"""Global test fixtures.

Injects the fake Earth Engine module (and lightweight stubs for heavy libs
that the pre-M5 fusion service imports but only uses in soon-deleted code) so
the suite runs offline with no GEE credentials. The injection is skipped when
ORBITER_GEE_LIVE=1, so M10's ``-m integration`` suite binds the REAL ``ee``.
"""
import os
import sys
import types

import pytest

_LIVE = os.environ.get("ORBITER_GEE_LIVE") == "1"


def _stub_if_absent(parent_name, child_name=None, attrs=None):
    """Register a stub module only if the real one can't be imported."""
    full = f"{parent_name}.{child_name}" if child_name else parent_name
    if full in sys.modules:
        return
    try:
        __import__(full)
        return  # real library present (e.g. on the Windows host) — use it
    except Exception:
        mod = types.ModuleType(full)
        for k, v in (attrs or {}).items():
            setattr(mod, k, v)
        sys.modules[full] = mod
        if child_name:
            setattr(sys.modules[parent_name], child_name, mod)


if not _LIVE:
    # 1) Fake Earth Engine.
    from tests.fakes import fake_ee

    sys.modules["ee"] = fake_ee

    # 2) Heavy/absent libs imported at module-top by the pre-M5 fusion service.
    #    All are only exercised by code deleted in M5; on Windows the real libs
    #    are present and these stubs are skipped.
    _stub_if_absent("PIL")
    _stub_if_absent("PIL", "Image")
    _stub_if_absent("scipy")
    _stub_if_absent("scipy", "ndimage")

    # 3) M6+ contract: app.main imports sentinel/landsat at module top, which
    #    pull in planetary_computer + pystac_client. On Windows the real
    #    packages are present; on the sandbox they aren't and TestClient-driven
    #    contract/error tests need a stub.
    def _stub_module(name, attrs=None):
        if name in sys.modules:
            return
        try:
            __import__(name)
            return
        except Exception:
            mod = types.ModuleType(name)
            for k, v in (attrs or {}).items():
                setattr(mod, k, v)
            sys.modules[name] = mod

    _stub_module("planetary_computer")
    # pystac_client.Client is what `from pystac_client import Client` needs.
    _stub_module("pystac_client", attrs={"Client": type("Client", (), {})})
    _stub_module("requests")


@pytest.fixture(autouse=True)
def _default_gee_project(monkeypatch):
    """Every test gets a valid project by default; config cache is reset."""
    monkeypatch.setenv("ORBITER_GEE_PROJECT", "test-project")
    import app.config as config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
