"""Earth Engine authentication resolver + lifespan state helper.

`init_earth_engine` is the ONLY place in the codebase that calls
`ee.Initialize`. It is a pure function of the Settings object, has no
hardcoded project, does not import the fusion service (no cycle), and never
runs at import time — only when the app lifespan calls it.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import ee

logger = logging.getLogger(__name__)

_HIGH_VOLUME_URL = "https://earthengine-highvolume.googleapis.com"


def init_earth_engine(cfg) -> None:
    """Initialize the global Earth Engine client from settings.

    Credential priority (highest first):
      1. Service-account JSON string  (ORBITER_GEE_SERVICE_ACCOUNT_JSON)
      2. Service-account key file      (ORBITER_GEE_SERVICE_ACCOUNT_FILE)
      3. Application Default Creds/ADC (`earthengine authenticate`)

    Uses the high-volume endpoint unless disabled. Raises on failure — the
    caller (lifespan) decides whether to degrade.
    """
    opt_url = _HIGH_VOLUME_URL if cfg.gee_high_volume else None
    project = cfg.gee_project

    if cfg.gee_service_account_json:
        info = json.loads(cfg.gee_service_account_json)
        creds = ee.ServiceAccountCredentials(
            info["client_email"], key_data=cfg.gee_service_account_json
        )
        ee.Initialize(credentials=creds, project=project, opt_url=opt_url)
        logger.info("GEE initialized via service-account JSON (project=%s)", project)
    elif cfg.gee_service_account_file:
        creds = ee.ServiceAccountCredentials(None, key_file=cfg.gee_service_account_file)
        ee.Initialize(credentials=creds, project=project, opt_url=opt_url)
        logger.info("GEE initialized via service-account file (project=%s)", project)
    else:
        ee.Initialize(project=project, opt_url=opt_url)
        logger.info("GEE initialized via Application Default Credentials (project=%s)", project)


def configure_gee_state(state: Any, cfg) -> None:
    """Best-effort GEE init that records readiness on an ``app.state``-like object.

    Sets ``state.gee_ready`` (bool) and ``state.gee_error`` (str | None). Never
    raises: a degraded backend still boots and serves an honest 503 from /health.
    """
    state.gee_ready = False
    state.gee_error = None
    try:
        init_earth_engine(cfg)
        state.gee_ready = True
    except Exception as e:  # noqa: BLE001 — degraded-safe by contract
        state.gee_error = str(e)
        logger.warning("GEE initialization failed; backend degraded: %s", e)
