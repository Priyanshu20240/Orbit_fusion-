"""M4 — registry seam behavior."""
import pytest

from app.services.fusion import STRATEGY_REGISTRY, get_strategy
from app.services.fusion.registry import FusionStrategy, VisSpec, register


def test_get_strategy_unknown_raises():
    with pytest.raises(KeyError):
        get_strategy("does_not_exist")


def test_registered_strategies_satisfy_protocol():
    for strat in STRATEGY_REGISTRY.values():
        assert isinstance(strat, FusionStrategy)
        assert isinstance(strat.id, str) and strat.sensors


def test_lst_is_landsat_only():
    assert get_strategy("lst").sensors == ["landsat"]


def test_register_returns_strategy():
    class _Dummy:
        id = "dummy_mode"
        sensors = ["sentinel"]

        def build(self, images):
            return None, VisSpec()

    d = _Dummy()
    assert register(d) is d
    assert get_strategy("dummy_mode") is d
    del STRATEGY_REGISTRY["dummy_mode"]  # keep the global registry clean
