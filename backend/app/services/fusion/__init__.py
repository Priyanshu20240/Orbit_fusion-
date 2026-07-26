"""Fusion engine (M4).

New, self-contained machinery for building masked/scaled composites and
minting getMapId tile templates. Additive in M4 — nothing in the live route
imports it until M5 wires ``build_fusion_map``.
"""
from .registry import (  # noqa: F401
    VisSpec,
    FusionStrategy,
    NoImageryError,
    STRATEGY_REGISTRY,
    register,
    get_strategy,
)
from . import strategies  # noqa: F401  — importing populates STRATEGY_REGISTRY
