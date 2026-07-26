"""Strategy registry seam.

P0 ships the current single-sensor views as strategies. Real fusion algorithms
(gap-fill, HLS harmonization, super-resolution) register here in later phases
without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable


@dataclass
class VisSpec:
    """getMapId visualization params (units already correct — LST is °C)."""
    bands: Optional[List[str]] = None
    min: float = 0.0
    max: float = 1.0
    gamma: float = 1.0
    palette: Optional[List[str]] = None
    provenance: str = "measured"  # "measured" | "modeled" | "synthetic-demo"
    citation: str = "Direct Multi-Spectral Reflectance (Sentinel-2 / Landsat SR)"


@runtime_checkable
class FusionStrategy(Protocol):
    """Structural type for a fusion strategy.

    Note: `experimental` is intentionally NOT in the Protocol. Phase 1 ships
    all 11 strategies as non-experimental; Phase 4 will mark the super-
    resolution strategy `experimental = True` as a class attribute. The
    invariant is locked by
    `tests/test_fusion_graph.py::test_experimental_default_false_for_every_strategy`.
    Putting `experimental` in the Protocol with a default value breaks
    `isinstance(strat, FusionStrategy)` because @runtime_checkable looks up
    attributes on the instance, not on the class.
    """
    id: str
    sensors: List[str]

    def build(self, images) -> Tuple[Any, VisSpec]:
        """Return (ee.Image to visualize, VisSpec)."""
        ...


class NoImageryError(Exception):
    """Raised when a fusion request matches zero scenes (→ HTTP 404 in M7)."""


STRATEGY_REGISTRY: "dict[str, FusionStrategy]" = {}


def register(strategy):
    """Register a strategy instance under its `id`. Returns it (usable as sugar)."""
    STRATEGY_REGISTRY[strategy.id] = strategy
    return strategy


def get_strategy(mode_id: str):
    try:
        return STRATEGY_REGISTRY[mode_id]
    except KeyError:
        raise KeyError(f"unknown visualization mode: {mode_id!r}")
