"""Typed application configuration (pydantic-settings).

Every setting is read from the environment with the ``ORBITER_`` prefix
(e.g. ``ORBITER_GEE_PROJECT``). ``gee_project`` is REQUIRED and fails loudly
at construction if unset — there is deliberately no hardcoded fallback
project (the old ``compact-arc-482620-r8`` default is gone for good).

Consumed by the GEE auth resolver (M2) and the CORS middleware (M3).
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORBITER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Google Earth Engine ──────────────────────────────────────────────
    gee_project: str  # REQUIRED — missing ⇒ ValidationError at startup
    gee_service_account_json: Optional[str] = None
    gee_service_account_file: Optional[str] = None
    gee_high_volume: bool = True

    # ── HTTP / CORS ──────────────────────────────────────────────────────
    # NoDecode: keep pydantic-settings from JSON-decoding the raw env value so
    # our validator can accept a plain comma-separated string as well as JSON.
    cors_origins: Annotated[List[str], NoDecode] = ["http://localhost:5173"]

    # ── Fusion tuning ────────────────────────────────────────────────────
    max_scenes_per_composite: int = 50
    default_cloud_cover: float = 20.0
    mapid_ttl_seconds: int = 21600  # 6 hours
    ee_threadpool_workers: int = 8

    # ── Phase 1: HLS harmonization ───────────────────────────────────────
    # Optional path to a JSON file with Claverie 2018 per-band [slope, intercept]
    # pairs. When unset, the operational HLS S30↔L30 v1.5 defaults in
    # services/fusion/scaling.py::HLSCoefficients are used. See PHASE1.md.
    hls_coeffs_path: Optional[str] = None

    # ── Phase 2: time-series tuning ──────────────────────────────────────
    # Upper bound on frames (per-scene acquisitions) returned by
    # /api/scenes/overlap. Matches the timelapse 50-frame cap.
    time_series_max_frames: int = 50
    # Concurrency cap for the frontend's per-frame loop. The backend's
    # ee_pool (ee_threadpool_workers) bounds the actual GEE work; this is
    # what the client loop respects.
    time_series_concurrency: int = 4

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v):
        """Accept a JSON list or a comma-separated string from the env."""
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                import json
                return json.loads(s)
            return [item.strip() for item in s.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Process-wide singleton. Call ``get_settings.cache_clear()`` in tests."""
    return Settings()
