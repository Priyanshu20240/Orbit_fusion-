"""M7 mapid cache.

Two process-local caches, keyed by the same hash ``build_fusion_map`` mints:

- ``_fusion_image_cache``: ``{fusion_id: (ee.Image, VisSpec)}`` — held so the
  ``/api/fusion/{fusion_id}/refresh-mapid`` endpoint can re-mint a mapid
  without re-running the composite + scaling + strategy pipeline. Cleared
  when a new request evicts an entry past ``maxsize``.

- ``_mapid_cache``: ``{fusion_id: {tile_url_template, mapid, expires_at}}`` —
  the *last* minted token, with a TTL backstop so a stale token never lives
  past ``mapid_ttl_seconds``. The primary refresh mechanism is *reactive*
  (frontend refetch on tile 4xx, design §C.3.4); the TTL is the safety net.

Both caches are single-process, which is what FastAPI/uvicorn gives us on a
single worker. If we move to multi-worker later, the cache must move to
Redis (or the workers each have their own — which is also fine for a
self-protective design where a 4xx is just a refetch).

``cachetools.TTLCache`` import is added in M9 alongside the dep audit; for
now a hand-rolled bounded dict is enough and keeps the diff small.
"""
from __future__ import annotations

import time
from typing import Any, Optional

#: {fusion_id: (ee.Image, VisSpec)}
_fusion_image_cache: dict[str, tuple[Any, Any]] = {}

#: {fusion_id: {"tile_url_template": str, "mapid": Optional[str], "expires_at": float_epoch}}
_mapid_cache: dict[str, dict[str, Any]] = {}

#: Process-wide size cap. Picked to comfortably exceed a single busy
#: viewport's worth of active layers (one per AOI × mode).
_MAX_ENTRIES = 64


def _evict_if_full(d: dict) -> None:
    """FIFO eviction so the cache can't grow without bound."""
    while len(d) > _MAX_ENTRIES:
        d.pop(next(iter(d)))


def store_fusion_image(fusion_id: str, image: Any, vis: Any) -> None:
    """Cache the (image, vis) pair built by build_fusion_map."""
    _fusion_image_cache[fusion_id] = (image, vis)
    _evict_if_full(_fusion_image_cache)


def load_fusion_image(fusion_id: str) -> Optional[tuple[Any, Any]]:
    return _fusion_image_cache.get(fusion_id)


def store_mapid(
    fusion_id: str,
    tile_url_template: str,
    mapid: Optional[str],
    ttl_seconds: int,
) -> float:
    """Cache a freshly-minted mapid. Returns its epoch-expiry."""
    expires_at = time.time() + ttl_seconds
    _mapid_cache[fusion_id] = {
        "tile_url_template": tile_url_template,
        "mapid": mapid,
        "expires_at": expires_at,
    }
    _evict_if_full(_mapid_cache)
    return expires_at


def load_mapid(fusion_id: str) -> Optional[dict[str, Any]]:
    """Return the cached mapid if it exists AND is not yet past TTL."""
    entry = _mapid_cache.get(fusion_id)
    if entry is None:
        return None
    if entry["expires_at"] <= time.time():
        # Lazy-evict the stale token.
        _mapid_cache.pop(fusion_id, None)
        return None
    return entry
