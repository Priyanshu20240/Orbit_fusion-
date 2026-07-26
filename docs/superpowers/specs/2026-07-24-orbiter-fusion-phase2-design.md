# Orbiter Fusion — Phase 2 (Harmonized Time Series) Design

**Date:** 2026-07-24 · **Status:** Draft for review · **Parent:** [roadmap](./2026-07-23-orbiter-fusion-roadmap.md) · **Builds on:** [phase 0 design](./2026-07-23-orbiter-fusion-phase0-design.md) · [phase 1 design](./2026-07-24-orbiter-fusion-phase1-design.md)

**Summary.** Phase 2 turns the single-frame "fire-and-forget" fusion of Phase 0/1 into a **real time axis**. It adds four things, all on top of the existing registry:

1. **A per-scene date axis.** Each GEE scene in the user's date range gets its own fusion mapid. The frontend loops the existing `POST /api/fusion/gee-harmonize` N times in parallel (one per scene) and caches the results as a `{date → layer}` map. The endpoint contract is **unchanged**.
2. **A rebuilt `TimeSlider.jsx`.** Replaces the placeholder comment at `Map.jsx:425-426` (Phase 0 deleted the prototype; Phase 2 re-introduces it as a real, per-scene, debounced, abort-aware scrubber).
3. **A swipe compare UI.** Two stacked layers, a vertical divider the user drags. Re-uses the existing `L.tileLayer` plumbing (no new mapids, just two `tile_layers` rendered in order with a `clip-path` on the top one). The compare pair is `(date A, date B)` from the time series, *or* `(sensor A, sensor B)` from the S2 vs L8 split.
4. **A re-plumbed timelapse UI.** The kept `/api/fusion/timelapse` endpoint already routes through the registry (Phase 0 §C.2.7). Phase 2 adds the "Play timelapse" button to the Sidebar — that's it. The endpoint is unchanged; the GIF URL is presented as a download link.

The Phase 1 `harmonized_l8` strategy is the natural substrate for the time series (every frame in a swiped pair uses the same HLS coefficients, so the colors match), but **no strategy changes** are required for Phase 2 — the time axis lives in the *frontend state* and in *N invocations of the existing endpoint*, not in the strategy registry.

**Locked decisions (user, 2026-07-24):**
- Per-date mapid: **loop `POST /api/fusion/gee-harmonize` per scene** (no new endpoint).
- Date buckets: **per-scene** (each GEE acquisition = one frame).
- Compare UI: **swipe** (two stacked layers + draggable divider).
- Timelapse: **re-add Sidebar control**, keep the existing GIF endpoint.

---

## A. Overview & locked decisions

**In scope (Phase 2):**
- A per-scene TimeSlider in the Map view (replaces `Map.jsx:425-426`'s trailing comment).
- A `useTimeSeries` hook that loops the existing fusion endpoint over scenes in parallel, with debounce + abort + cache.
- A swipe compare UI: two layers, draggable vertical divider, geometry-only (no second mapid needed).
- A Sidebar "Play timelapse" button that calls the existing `/api/fusion/timelapse` and presents the GIF as a download link.
- One new backend endpoint: `POST /api/scenes/overlap` (returns the per-scene date list for a `(bounds, date_range, platforms)` query — a thin STAC search wrapper; the frontend uses it to populate the TimeSlider frames). The existing search already returns per-scene datetimes; the new endpoint just shapes them for the TimeSlider.
- New reducer actions for the time series + compare axes.
- New `LayerControl` / sidebar UI for the swipe pair selector and the timelapse button.
- A re-introduced `TimeSlider.jsx` (the Phase 0 plan explicitly deferred it to Phase 2; the prototype was deleted in M9).

**Out of scope (Phase 2):**
- ML super-resolution (Phase 4).
- GeoTIFF export (Phase 3).
- Re-tuning the HLS coefficients in-tree (the env-var override is already the escape hatch from Phase 1).
- A "rebuild the time series" button after AOI/date change beyond a passive re-fetch on input change (no manual "Refresh time series" button — the slider re-fetches when AOI/date range/platforms/viz changes).
- Server-side caching of the per-scene images (the per-scene `ee.Image` does not survive across requests; we only cache the *mapid* per fusion_id, same as today).
- Per-scene provenance (which sensor filled which pixel) — that needs a per-pixel band, which is its own change to the strategies and is [LATER].
- A custom leaflet-compare plugin — the swipe is implemented with a single `clip-path` and an `mousemove` handler, no new dep.
- Spinning up a worker pool / queue for the per-scene GEE calls — the existing `app.state.ee_pool` (ThreadPoolExecutor, 8 workers) handles the parallel loop on the *frontend* side, and the *backend* already runs each fusion in its own pool call.

**Locked decisions (carry-over from Phase 0 + Phase 1):**
- Stay on GEE. Stay on `image.getMapId(vis)` XYZ tiles. Stay on the registry seam. Stay on the `ORBITER_` env prefix.
- Backend fusion contract (`POST /api/fusion/gee-harmonize` returning `FusionMapResponse`) is **unchanged** for Phase 2.
- Frontend: no new dependencies. The swipe uses a CSS `clip-path` + a draggable absolutely-positioned div. No `leaflet-compare` plugin.
- The 11 registry strategies are unchanged. Phase 2 doesn't add a 12th strategy.

---

## B. Roadmap (no change; restated for completeness)

| Phase | Deliverable | Status |
|---|---|---|
| Phase 0 — Foundation | registry seam, masked composites, correct indices, LST °C, honest errors, CI | ✅ COMPLETE |
| Phase 1 — Real Fusion I | `gap_fill` + `harmonized_l8` + `real_lst` | ✅ COMPLETE |
| **Phase 2 — Harmonized time series** | **Per-scene TimeSlider, swipe compare, timelapse re-plumbed (this doc)** | 🔜 NOW |
| Phase 3 — Spectral extension + export | GeoTIFF/PNG via async `getDownloadURL`; `ExportPanel` returns | [LATER] |
| Phase 4 — Super-resolution (experimental) | PyTorch SR model, `experimental=True` gate, fidelity metric | [LATER] |

---

## C. Phase 2 — Detailed design

### C.1 The data model — what a "frame" is

A **frame** is one (scene, mode) pair → one `FusionMapResponse`. Concretely:

```python
# Frontend state shape (LayersContext), additive over Phase 0/1:
{
  layers: [
    { id, kind, mode, tileUrl, ..., kind: "gee" },     # the active frame (current scrub)
    { id, kind: "swipe-compare", slot: "B", tileUrl, ... },  # the comparison slot
    # ...
  ],
  timeSeries: {
    window: { startDate, endDate },
    frames: [
      { date: "2024-01-15", sensor: "sentinel", fusionId, tileUrl, sceneCounts, ready: true },
      { date: "2024-01-21", sensor: "landsat",  fusionId, tileUrl, sceneCounts, ready: true },
      ...
    ],
    currentFrameIdx: 5,           # which frame is the active layer
    loading: false,
    error: null,
  },
  compare: {
    enabled: false,
    slotA: 5,                     # frame idx for the left side
    slotB: 8,                     # frame idx for the right side
    dividerX: 0.5,                # 0..1 of map width
  },
}
```

**Key invariants:**
- The active layer is *always* `layers[ timeSeries.currentFrameIdx ]`. There is exactly one fusion layer in the `layers` array at any time; the slider swap is a `LAYER_UPDATED` (re-points the `tileUrl` and `fusionId`) — not a `LAYER_ADDED` + `LAYER_REMOVED`. This keeps the click-race test (M8b) honest: the data-testid is on the layer container, not on a per-frame id.
- The compare slot is a *separate* `L.tileLayer` added on top, clipped to the right of the divider. It is **not** in the `layers` array (which the LayerControl iterates over); it's a peer of the active layer owned by a new `SwipeCompare` component.
- The `timeSeries.frames[].fusionId` is the *same* md5 hash that the backend mints today (`hashlib.md5(bounds|start|end|vis|sorted(platforms))[:12]`) — re-pointing the active layer at a different frame is just a swap of the `fusionId` and `tileUrl`. The `refresh-mapid` cache path works as-is for each frame.

### C.2 Backend: `POST /api/scenes/overlap` — the per-scene date list

The TimeSlider needs the **list of per-scene dates** for the current `(bounds, date_range, platforms)` so it can show tick marks, label each frame, and let the user click a date to jump there. The existing `/api/search/all` already returns per-scene `datetime` (from STAC), but it returns the full STAC scene objects (clouds, geometry, thumbnail URLs) — the TimeSlider just needs dates and sensor names.

**The new endpoint is a thin shape-only wrapper around the existing search.**

```python
# backend/app/models/schemas.py — add to the file
class SceneDateEntry(BaseModel):
    """One per-scene date in the time-series overlap window."""
    date: date                                 # the acquisition date (STAC `datetime`, day-rounded)
    sensor: Literal["sentinel", "landsat"]
    scene_id: str                              # STAC id
    cloud_cover: Optional[float] = None

class ScenesOverlapResponse(BaseModel):
    frames: List[SceneDateEntry]                # sorted by date asc
    bucket: Literal["scene"] = "scene"          # future: "month" | "quarter" (not in Phase 2)


# backend/app/routers/scenes.py — NEW FILE
from fastapi import APIRouter
from app.models.schemas import SearchRequest, ScenesOverlapResponse, SceneDateEntry
from app.services.sentinel import sentinel_service
from app.services.landsat import landsat_service
from app.core.concurrency import run_in_pool
from app.main import app
import asyncio

router = APIRouter()

@router.post("/api/scenes/overlap", response_model=ScenesOverlapResponse)
async def scenes_overlap(request: SearchRequest):
    """Return the per-scene date list for the (bounds, date_range, platforms) query.
    
    This is the *time axis* of the TimeSlider: one entry per GEE acquisition, sorted
    by date. The frontend caches this and loops the existing /api/fusion/gee-harmonize
    once per entry to mint a per-scene mapid (Phase 2 §C.1).
    """
    bbox = request.bbox.to_list()
    kwargs = dict(
        bbox=bbox,
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit or 50,
    )
    sentinel_result, landsat_result = await asyncio.gather(
        run_in_pool(app.state.ee_pool, sentinel_service.search_scenes, **kwargs),
        run_in_pool(app.state.ee_pool, landsat_service.search_scenes, **kwargs),
    )
    frames: list[SceneDateEntry] = []
    for scene in sentinel_result.get("scenes", []):
        d = _parse_date(scene.get("datetime", ""))
        if d is None: continue
        frames.append(SceneDateEntry(
            date=d, sensor="sentinel",
            scene_id=scene["id"],
            cloud_cover=scene.get("cloud_cover"),
        ))
    for scene in landsat_result.get("scenes", []):
        d = _parse_date(scene.get("datetime", ""))
        if d is None: continue
        frames.append(SceneDateEntry(
            date=d, sensor="landsat",
            scene_id=scene["id"],
            cloud_cover=scene.get("cloud_cover"),
        ))
    frames.sort(key=lambda e: e.date)
    return ScenesOverlapResponse(frames=frames)


def _parse_date(s: str):
    """STAC `datetime` is RFC 3339 (e.g. '2024-01-15T05:23:11.000Z'). Day-round to date."""
    from datetime import datetime, date
    if not s: return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None
```

**Why a new endpoint, not just `/api/search/all`.** The frontend already uses `/api/search/all` to populate the "Results (N scenes)" panel. The TimeSlider needs a *different shape* (just dates + sensor + scene_id, no clouds/geometry/thumbnails). Mixing the two would force the frontend to re-shape one or the other. The new endpoint is a 30-LOC thin shim and the test surface is one new endpoint-contract test.

**Bucket = "scene" only.** The Phase 2 design hard-codes per-scene bucketing. A `month` bucket is a `[LATER]` knob (the `bucket` field is in the response so the frontend can detect it; the request side just always sends "scene" for now).

### C.3 Frontend: `useTimeSeries` — the per-scene loop

```js
// frontend/src/hooks/useTimeSeries.js
//
// New hook for Phase 2. Drives the TimeSlider.
//
// 1. When the user changes aoi / dateRange / platforms (and only after search has
//    succeeded, so we have the aoi), dispatch TIME_SERIES_REQUESTED to the
//    layers context. Fire /api/scenes/overlap to get the per-scene date list.
// 2. When the per-scene list comes back, dispatch TIME_SERIES_FRAMES_LOADED
//    with the frames. State now has frames[] but ready=false for all of them.
// 3. Loop the existing /api/fusion/gee-harmonize in parallel, one per frame,
//    with a configurable concurrency cap (default 4, configurable via
//    ORBITER_TIMESERIES_CONCURRENCY env → settings → SettingsContext).
// 4. As each frame resolves, dispatch TIME_SERIES_FRAME_READY with the
//    (date → fusionId, tileUrl) patch. The slider's thumb updates.
// 5. When the user moves the slider, TIME_SERIES_SET_CURRENT dispatches; the
//    active layer is LAYER_UPDATED to point at the new frame's tileUrl/fusionId.
//
// AbortController: any new dispatch (e.g. a search refresh, a date-range
// change, an explicit "cancel") aborts the in-flight loop. Stale-winner
// guard is per-frame, same as M8b.
```

**Concurrency cap.** The existing `app.state.ee_pool` has 8 workers. Defaulting the frontend to 4 concurrent loops keeps headroom. The cap is configurable via the new `Settings.time_series_concurrency` (env: `ORBITER_TIMESERIES_CONCURRENCY`, default 4).

**Cache key.** `(bounds, visualization, platforms, date)`. The per-frame `fusionId` is the *backend's* md5 of `(bounds|date|date|vis|platforms)` — the frontend doesn't have to compute it; the loop just stores the response's `fusion_id`.

**Caching.** The per-frame mapid is cached on the backend (`mapid_cache`) for `mapid_ttl_seconds` (6 h). The frontend caches the `{date → {fusionId, tileUrl}}` map in the layers context (not in `localStorage` — it's a session cache, and the user can re-fetch).

### C.4 Frontend: `TimeSlider.jsx` — the scrubber

```jsx
// frontend/src/components/TimeSlider.jsx
//
// New component. Renders below the map, above the basemap-attribution row.
//
// Props (all from LayersContext via useTimeSeries):
//   - frames: [{ date, sensor, fusionId, tileUrl, sceneCounts, ready, cloudCover }]
//   - currentIdx: number
//   - onScrub: (idx) => void
//   - onPlay: () => void            (kicks the auto-advance for timelapse UX)
//   - playing: boolean
//   - disabled: boolean
//
// Renders:
//   ◀◀  [thumb]  ▶▶
//   tick marks (one per frame; tick = small vertical line)
//   sensor badge per tick (S2 = cyan, L8 = orange)
//   current date in bold above the thumb
//   play/pause button on the right
//
// Keyboard:
//   ← / →            jump one frame
//   shift+← / →      jump 5 frames
//   space            play/pause
//   home / end       first / last frame
//
// A11y:
//   role="slider" with aria-valuemin/max/now + aria-valuetext="<date>, <sensor>"
//   aria-label="Time slider"
//   live region announces date on scrub (debounced)
//
// Implementation:
//   - Single horizontal div, width = 100% of map width minus 24px padding.
//   - Thumb = a 12px-wide absolutely-positioned div, left = (currentIdx /
//     (frames.length - 1)) * 100%. Pointer events: pointerdown → setPointerCapture
//     → pointermove updates local "scrubbing" state without dispatch (just visual
//     drag); pointerup dispatches TIME_SERIES_SET_CURRENT with the final idx.
//   - During drag, no GET — we just preview. The GET only fires on pointerup
//     (or on keyboard arrow, which is a discrete dispatch).
//   - Tick marks: small divs, one per frame, sensor-coloured.
//   - Play: setInterval(advance, 750ms) until end or user pause.
```

**Where it mounts.** `Map.jsx:425-426` has the placeholder `{/* Time Slider */}`. Phase 2 replaces that with `<TimeSlider … />` (always rendered; empty frames → component hidden).

**Behaviour when frames[] is empty (no search run, or search returned 0 scenes).** Component is hidden. The Sidebar still shows the search button.

### C.5 Frontend: `SwipeCompare.jsx` — the divider

```jsx
// frontend/src/components/SwipeCompare.jsx
//
// New component. Sits inside Map.jsx, rendered above the basemap and below
// the AOI/coords overlays. Owns the "slot A" + "slot B" layer refs.
//
// State (from LayersContext):
//   - enabled: boolean             (compare toggle)
//   - slotA: { date, sensor, fusionId, tileUrl }   (from timeSeries.frames[idx])
//   - slotB: same shape
//   - dividerX: 0..1               (drag handle position)
//
// Render:
//   - Always render slotA as a regular L.tileLayer (added to the map once,
//     not removed when divider moves; it just gets progressively hidden by
//     the slotB clip-path).
//   - When enabled: render slotB as a SECOND L.tileLayer on top, with
//     `opacity: 1.0` and a CSS clip-path that masks everything LEFT of the
//     divider. Pure CSS — no leaflet-compare plugin.
//   - Vertical divider: a 2px-wide absolutely-positioned div at left =
//     dividerX * 100%. Cursor: ew-resize. Pointer events to drag.
//   - A small "B" badge on the slotB side; an "A" badge on the slotA side.
//     (Helpful for the user to know which side is which when the modes differ.)
//
// A11y:
//   - Divider is keyboard-accessible: role="separator", aria-orientation="vertical",
//     aria-valuenow, focusable, arrow keys nudge by 1%.
//
// The compare pair is selected via two slot pickers in the LayerControl
// (or in a new "Compare" section of the Sidebar). Each picker is a
// <select> over the timeSeries.frames[] list, filtered by sensor if the
// user has only one platform enabled.
```

**Implementation detail — clip-path.** Slot B's `<div>` (the one wrapping its `L.tileLayer.getContainer()`) gets `style={{ clipPath: `inset(0 0 0 ${dividerX * 100}%)` }}`. `inset(0 0 0 X%)` means "clip from the top, right, bottom, and **left X%**" — that's the right side. Drag the divider → update `dividerX` → re-clip.

**Two layers, two mapids.** Slot A is the active fusion layer; slot B is a peer L.tileLayer on top with a clip. Both have real mapids (the per-frame mapids from the time series cache). The compare is geometry only — no second backend call.

### C.6 Frontend: timelapse UI re-plumb

The backend `POST /api/fusion/timelapse` (kept, registry-routed in Phase 0 §C.2.7) returns `{ success: true, url: "https://...", count: N }` — a GEE `getVideoThumbURL` for a GIF. Phase 2 wires the Sidebar to it:

```jsx
// Sidebar.jsx — Phase 2 addition (the only timelapse control)
<button
  type="button"
  className="btn btn-secondary btn-block"
  onClick={onTimelapse}
  disabled={isProcessingTimelapse || !aoi || !timeSeriesReady}
>
  {isProcessingTimelapse
    ? "⏳ Generating timelapse…"
    : "🎬 Generate timelapse GIF"}
</button>
{ timelapseUrl && (
  <a href={timelapseUrl} target="_blank" rel="noopener noreferrer"
     className="btn btn-link btn-block">
    ⬇️ Download timelapse ({frameCount} frames)
  </a>
) }
```

State lives in the layers context: `timelapse: { url, count, loading, error }`. The button calls `onTimelapse` → `useTimelapse` hook → POSTs to `/api/fusion/timelapse` with the current `(bounds, start_date, end_date, platform, visualization)`. The endpoint already works; the hook + button are the only new code.

**No contract change.** The endpoint is identical to its M5 form (re-plumbed in M5 to route through the registry).

### C.7 Reducer + actions

New action types in `state/actions.js`:

```js
export const TIME_SERIES_REQUESTED = "TIME_SERIES_REQUESTED";
export const TIME_SERIES_FRAMES_LOADED = "TIME_SERIES_FRAMES_LOADED";
export const TIME_SERIES_FRAME_READY = "TIME_SERIES_FRAME_READY";
export const TIME_SERIES_FAILED = "TIME_SERIES_FAILED";
export const TIME_SERIES_SET_CURRENT = "TIME_SERIES_SET_CURRENT";
export const TIME_SERIES_CLEAR = "TIME_SERIES_CLEAR";
export const COMPARE_TOGGLED = "COMPARE_TOGGLED";
export const COMPARE_SLOT_CHANGED = "COMPARE_SLOT_CHANGED";
export const COMPARE_DIVIDER_MOVED = "COMPARE_DIVIDER_MOVED";
export const TIMELAPSE_STARTED = "TIMELAPSE_STARTED";
export const TIMELAPSE_SUCCEEDED = "TIMELAPSE_SUCCEEDED";
export const TIMELAPSE_FAILED = "TIMELAPSE_FAILED";
```

Reducer additions in `state/reducer.js` (the `timeSeries`, `compare`, `timelapse` slices of the layers context; all additive, no breaking change to existing actions).

**The active-layer swap on `TIME_SERIES_SET_CURRENT`.** The current frame's `tileUrl` + `fusionId` are applied to the *existing* active layer via `LAYER_UPDATED`. This is what makes the click-race + refresh-mapid tests still pass: the `data-testid="layer-${mode}"` is on the *layer container*, and the layer container is the same DOM node across the slider scrub.

### C.8 Sidebar additions

Three new sections (inserts, not rewrites):

1. **Time Series** — shown when `searchResults` has any entries. Tells the user "N scenes in window"; lets them enable the time axis (default off; off → existing single-fusion behaviour, which is what Phase 0/1 shipped).
2. **Compare** — shown when time series is enabled + ≥2 frames. Two slot pickers (slot A = current frame; slot B = choose any other frame in the window). The "Enable compare" toggle. The compare pair can also be a sensor-vs-sensor pair (S2 | L8) when both sensors are selected.
3. **Timelapse** — a single button (see §C.6) shown when AOI is set and the time series has at least one frame.

### C.9 Map.jsx changes

- Delete the dead props `isTimeLapsePlaying / onTimeLapseToggle / onTimeSliderChange` from the function signature (`Map.jsx:47`).
- Replace the trailing `{/* Time Slider */}` placeholder (`Map.jsx:425-426`) with `<TimeSlider />` and `<SwipeCompare />` (the latter only when compare is enabled).
- The `useEffect` that manages tile layers (`Map.jsx:195-316`) needs one addition: when the active layer's `tileUrl` changes (because the slider moved), call `leafletLayer.setUrl(newUrl)` instead of removing/re-adding. This keeps the layer container (and its data-testid) stable across frame swaps — which is the invariant the click-race test relies on.

### C.10 Config + env

Two new fields, both optional:

```python
# backend/app/config.py — additions
time_series_max_frames: int = 50          # ORBITER_TIME_SERIES_MAX_FRAMES (cap frames per request)
time_series_max_scenes_per_frame: int = 1 # ORBITER_TIME_SERIES_MAX_SCENES_PER_FRAME (composite per date)
```

The cap is a safety net for the frontend's loop (the backend's own `max_scenes_per_composite` is already in use; this is the upper bound on *frame count*, not scenes per frame). Default 50 matches the timelapse cap (50 frames, `gee_fusion_service.py:291`).

No new frontend env vars.

### C.11 Tests

**Backend (new).**

| File | Test | What it locks |
|---|---|---|
| `tests/test_scenes_overlap.py` | `test_overlap_returns_sorted_unique_dates` | The new endpoint returns dates sorted asc, deduplicated by (date, sensor, scene_id). |
| `tests/test_scenes_overlap.py` | `test_overlap_clamps_to_limit` | `limit=10` returns at most 10 frames. |
| `tests/test_scenes_overlap.py` | `test_overlap_handles_no_scenes` | Empty search → 200 with `frames: []`. |
| `tests/test_scenes_overlap.py` | `test_overlap_uses_concurrent_search` | Sentinel and Landsat searches run concurrently (asserted via the `concurrent.futures` threadpool, not GEE). |
| `tests/test_endpoints_contract.py` | `test_scenes_overlap_route_present` | `POST /api/scenes/overlap` is registered exactly once. |

**Frontend (new).**

| File | Test | What it locks |
|---|---|---|
| `src/test/timeseries.test.js` | `test_per_frame_loop_uses_abort_controller` | The hook's per-frame loop is aborted when a new dispatch lands; no stale frames get into state. |
| `src/test/timeseries.test.js` | `test_set_current_dispatches_layer_updated_with_same_id` | The active layer's id is preserved across slider swaps; the same `data-testid` is hit. |
| `src/test/timeseries.test.js` | `test_slider_keyboard_arrow_jumps_one_frame` | ← / → dispatch `TIME_SERIES_SET_CURRENT` with idx ± 1. |
| `src/test/timeseries.test.js` | `test_compare_toggle_adds_a_second_layer` | The compare pair is a second L.tileLayer on top; the active layer's id is unchanged. |
| `src/test/timeseries.test.js` | `test_compare_divider_drag_updates_clip_path` | Pointer drag on the divider updates `dividerX` and the slotB's `clip-path`. |
| `src/test/timeseries.test.js` | `test_timelapse_button_calls_existing_endpoint` | The timelapse control POSTs to `/api/fusion/timelapse` with the same `TimelapseRequest` shape; the response's `url` becomes the download link. |

**No regression.** All 84 backend tests from Phase 0/1 still pass; the 5 frontend tests still pass.

---

## D. Success criteria (Phase 2 measurable)

A Phase 2 is "done" when **all** hold:

1. **Per-scene date list endpoint.** `POST /api/scenes/overlap` returns 200 with `frames: [{date, sensor, scene_id, cloud_cover?}]` sorted asc, for any `(bounds, date_range, platforms)` triple.
2. **TimeSlider renders.** A real `<TimeSlider />` component is mounted in the Map view, below the map and above the basemap-attribution row. Renders one tick per frame; current frame is highlighted; ←/→/space/home/end all work.
3. **Slider swap is a single `setUrl` call.** Moving the slider does **not** remove/re-add the active layer; the data-testid `layer-${mode}` is stable across frame swaps.
4. **Swipe compare works.** Two layers stacked, draggable vertical divider, slot A = current frame, slot B = any other frame. Divider drag updates `clip-path` only; no second backend call.
5. **Timelapse button works.** The Sidebar has a "Generate timelapse GIF" button that calls the existing `/api/fusion/timelapse`; the response's `url` is presented as a download link.
6. **Endpoint contract preserved.** `POST /api/fusion/gee-harmonize` and `GET /api/fusion/{fusion_id}/refresh-mapid` are unchanged; all 11 registry strategies still reachable; `POST /api/fusion/timelapse` is unchanged.
7. **No new dependencies.** `requirements.txt` and `package.json` are unchanged from Phase 1. The compare uses CSS `clip-path`, not a leaflet plugin.
8. **AbortController across the loop.** A new search refresh (or a date-range change) aborts the in-flight per-frame loop; stale frames do not leak into state.
9. **Test gates still hold.** Backend coverage ≥ 75%; frontend coverage ≥ 55%. All 84 existing backend tests pass; all 5 existing frontend tests pass.
10. **CI is green.** Backend + frontend jobs in CI pass on the new code. The integration test suite (gated by `ORBITER_GEE_LIVE=1`) still runs against the unchanged `gee-harmonize` endpoint.

---

## E. Open questions (resolved by user, 2026-07-24)

| # | Question | Resolution |
|---|---|---|
| 1 | Per-date mapid: loop the existing endpoint vs new `/api/fusion/time-series`? | **Loop the existing endpoint.** No new fusion endpoint. |
| 2 | Date buckets: per-scene vs per-month vs best-on-date? | **Per-scene.** Each GEE acquisition = one frame. |
| 3 | Compare UI: swipe vs spyglass vs side-by-side panels? | **Swipe.** Two stacked layers + draggable divider (CSS `clip-path`). |
| 4 | Timelapse re-plumb: re-add control + keep GIF, skip timelapse, or re-add control + use mp4? | **Re-add Sidebar control, keep the existing GIF endpoint.** |

---

## F. Out of scope for Phase 2 (restated for clarity)

- Per-pixel provenance band (a strategy-level change; `[LATER]`).
- Pre-expiry proactive mapid-refresh timer (Phase 0 deferred; the tile-4xx reactive refetch still works).
- GeoTIFF/PNG export (`ExportPanel`, `create_dataset`) — Phase 3.
- Super-resolution — Phase 4, experimental.
- Re-fitting HLS coefficients in-tree — the env-var override is the escape hatch.
- A "month bucket" TimeSlider mode — the response shape leaves room for it (`bucket: 'scene' | ...`) but the request side hard-codes `'scene'` in Phase 2.
- A `leaflet-compare` plugin or any new frontend dependency.

---

## G. What I'm explicitly **not** doing in Phase 2

- **Re-shaping `FusionMapResponse`.** Per-frame mapid is the same shape as today's single-fusion response. The frontend caches the `{date → FusionMapResponse}` map.
- **Server-side fan-out of the per-frame loop.** The frontend does the loop; the backend handles one fusion per request. (A server-side fan-out would couple the backend to a "time axis" notion that doesn't exist in the strategy registry.)
- **A new "time series" strategy.** The 11 existing strategies all work on a per-image `ee.Image`; the time axis is *outside* the strategy.
- **A monthly/quarterly bucket.** Locked at per-scene.
- **Spyglass / magnifier compare.** Locked at swipe.
- **MP4 timelapse.** Locked at GIF (the existing `getVideoThumbURL` output).
