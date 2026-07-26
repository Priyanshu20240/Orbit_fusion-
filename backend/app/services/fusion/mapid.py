"""Mint a getMapId XYZ tile template from an ee.Image + VisSpec.

This is the pivot away from server-side PNG download: instead of rendering
raster on the backend, GEE serves XYZ tiles and we hand the browser the
`{z}/{x}/{y}` template.
"""
from __future__ import annotations

from typing import Any, Optional

from .registry import VisSpec


def visspec_to_vis(vis: VisSpec) -> dict:
    """Translate a VisSpec into the dict getMapId expects."""
    out: dict[str, Any] = {"min": vis.min, "max": vis.max}
    if vis.bands:
        out["bands"] = vis.bands
    if vis.gamma and vis.gamma != 1.0:
        out["gamma"] = vis.gamma
    if vis.palette:
        out["palette"] = vis.palette
    return out


def mint_mapid(image, vis: VisSpec, ttl: Optional[int] = None) -> dict:
    """Return ``{"tile_url_template", "mapid"}`` for the given image + vis.

    `ttl` is accepted for caller symmetry (the cache TTL lives in M7's
    mapid_cache); minting itself is stateless.
    """
    map_id = image.getMapId(visspec_to_vis(vis))

    tile_fetcher = map_id.get("tile_fetcher") if isinstance(map_id, dict) else None
    url = getattr(tile_fetcher, "url_format", None)
    if not url:
        # Fallback for older ee return shapes ({mapid, token}).
        mid = map_id.get("mapid") if isinstance(map_id, dict) else str(map_id)
        url = f"https://earthengine.googleapis.com/v1/{mid}/tiles/{{z}}/{{x}}/{{y}}"

    return {"tile_url_template": url, "mapid": map_id.get("mapid") if isinstance(map_id, dict) else None}
