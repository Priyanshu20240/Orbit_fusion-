# Phase 2 — Harmonized Time Series

**Status: COMPLETE.** Phase 2 turns the single-frame "fire-and-forget" fusion
of Phase 0/1 into a real **time axis**. It adds four things, all on top of
the existing registry seam and the unchanged `/api/fusion/gee-harmonize`
endpoint.

Full design: [docs/superpowers/specs/2026-07-24-orbiter-fusion-phase2-design.md](./docs/superpowers/specs/2026-07-24-orbiter-fusion-phase2-design.md)
Full plan: [docs/superpowers/specs/2026-07-24-orbiter-fusion-phase2-plan.md](./docs/superpowers/specs/2026-07-24-orbiter-fusion-phase2-plan.md)

## What landed

| Feature | What it does | Substrate |
|---|---|---|
| **`POST /api/scenes/overlap`** | Returns the per-scene date list for `(bounds, date_range, platforms)`. The TimeSlider's data source. | A thin wrapper around `sentinel_service.search_scenes` + `landsat_service.search_scenes` (concurrent via `asyncio.gather`). |
| **`useTimeSeries` hook** | Loops the existing `/api/fusion/gee-harmonize` once per frame (start_date == end_date), in parallel, with an `AbortController` for click-race safety. Concurrency cap defaults to 4. | Existing fusion endpoint. No new backend call shape. |
| **`<TimeSlider>` component** | Renders the per-scene date axis below the map. Pointer drag, keyboard (←/→/space/home/end), ARIA `role="slider"`. Sensor-coloured ticks (S2 cyan, L8 orange). | Frames from the hook + the per-frame mapids. |
| **`<SwipeCompare>`** | Two layers stacked, vertical divider, draggable. Slot A = current frame; slot B = any other frame. Pure CSS `clip-path`, no leaflet plugin. | A second `L.tileLayer` in `Map.jsx` with a clip-path on its container. |
| **Timelapse UI re-plumb** | Sidebar "🎬 Generate timelapse GIF" button calls the existing `/api/fusion/timelapse` endpoint. The response's `url` is presented as a download link. | The Phase 0 timelapse endpoint (kept, registry-routed). |

The `harmonized_l8` strategy from Phase 1 is the **natural substrate** for
the per-scene frames — every frame in a swiped pair uses the same HLS
coefficients, so the colors match. **No strategy changes** were required
for Phase 2.

## Endpoint contract — unchanged

`POST /api/fusion/gee-harmonize` returns the same `FusionMapResponse` shape
for all 11 modes. The TimeSlider loop uses that endpoint N times (one per
frame), with `start_date == end_date == frame.date`.

`GET /api/fusion/{fusion_id}/refresh-mapid` works for each per-frame mapid
the same way it works for today's single-fusion responses.

`POST /api/fusion/timelapse` is unchanged.

The only **new** endpoint is `POST /api/scenes/overlap` (see below).

## How to use the new UI

After the operator runs the app, the new flow is:

1. Draw an AOI on the map, select Sentinel-2 + Landsat, pick a date range,
   click **Search**.
2. The TimeSlider appears below the map, showing one tick per GEE
   acquisition in the window. The current frame is the most recent
   acquisition in the date range.
3. **Drag the thumb** (or use ← / → / Home / End) to scrub through the
   dates. The active layer re-points to the selected frame's mapid; the
   data-testid container is stable across scrub (M8b invariant).
4. **Enable compare** to see two frames side-by-side. The two slot
   pickers choose which dates go on the left and right; the divider is
   draggable.
5. **Generate timelapse GIF** at the bottom of the Sidebar to call
   `/api/fusion/timelapse` and download the GIF.

## The new endpoint

```
POST /api/scenes/overlap
{
  "bbox": { "min_lon": ..., "min_lat": ..., "max_lon": ..., "max_lat": ... },
  "start_date": "2024-01-01",
  "end_date": "2024-03-31",
  "max_cloud_cover": 30,
  "limit": 50
}

→ 200 OK
{
  "frames": [
    { "date": "2024-01-15", "sensor": "sentinel", "scene_id": "...", "cloud_cover": 5.0 },
    { "date": "2024-01-20", "sensor": "landsat",  "scene_id": "...", "cloud_cover": 8.0 },
    ...
  ],
  "bucket": "scene"
}
```

Frames are sorted by date asc, deduped on `(date, sensor, scene_id)`,
capped at `ORBITER_TIME_SERIES_MAX_FRAMES` (default 50). The `limit`
field from the request is forwarded to the underlying search services.

## Overriding the concurrency cap

The frontend's per-frame loop respects `ORBITER_TIME_SERIES_CONCURRENCY`
(default 4). Lower it if you have a small GEE pool; raise it for faster
local-dev iteration. The backend's `ORBITER_EE_THREADPOOL_WORKERS`
(default 8) bounds the actual GEE work — keep the loop concurrency ≤
the pool size to avoid queueing.

## Test surface

| File | Tests added | What they lock |
|---|---|---|
| `backend/tests/test_scenes_overlap.py` | +9 | Sort + dedup, limit forwarding, empty results, malformed datetime tolerance, scene_id requirement, concurrent search (asyncio.gather), `ORBITER_TIME_SERIES_MAX_FRAMES` cap, route uniqueness, 422 on bad body. |
| `frontend/src/test/reducer.test.js` | +14 | 11 new action types + 3 new state slices; the **headline invariant** that `TIME_SERIES_SET_CURRENT` patches the active layer in place (no new layer added — M8b click-race test still passes). |
| `frontend/src/test/timeseries.test.js` | +4 | Per-frame loop aborts on redispatch, `TIME_SERIES_SET_CURRENT` does NOT add a new layer, concurrency cap respected, in-flight loop aborts on `TIME_SERIES_CLEAR`. |
| `frontend/src/test/timeslider.test.js` | +4 | One tick per frame, hides on empty, keyboard ←/→/Home/End, pointer drag commits `TIME_SERIES_SET_CURRENT` on pointerup. |
| `frontend/src/test/swipe-compare.test.js` | +7 | Renders nothing when disabled / frames<2, pointer drag, keyboard arrow (±0.02 / ±0.10 with shift), `COMPARE_SLOT_CHANGED`. |
| `frontend/src/test/timelapse.test.js` | +4 | Sidebar button calls onTimelapse, download link with the right href + frame count, disabled when loading. |
| `frontend/src/test/handlers.js` | +1 handler | `POST /api/fusion/timelapse` MSW handler. |

**Backend test count: 93** (84 baseline + 9 new). All pass in the sandbox.
**Frontend test count: 26** (5 baseline + 21 new) — verifiable on the
Windows host via `npm test`.

## M8b invariant (preserved)

The `data-testid="layer-${mode}"` container on the active GEE tile layer
**survives a slider scrub**. The implementation in `Map.jsx` (the
`useEffect` at the tile-layer management block) calls
`leafletLayer.setUrl(newUrl)` when the layer's `tileUrl` changes — it
**never** remove+re-adds the layer for a slider scrub. The M8b
click-race test (`src/test/click-race.test.js`) still passes.

## Known limitations (deliberate)

| Limitation | Why | [LATER] upgrade |
|---|---|---|
| Per-pixel provenance band not added | First consumer is the time-series scrubber (which doesn't display provenance). | A Phase 2.5 or Phase 3 strategy that emits a `provenance` band. |
| Per-month bucketing not implemented | Locked at per-scene per the design's user decision. | A `bucket: 'month' | 'quarter'` knob; the response's `bucket` field already leaves room. |
| Proactive pre-expiry mapid-refresh not implemented | Tile-4xx reactive refetch (Phase 0) still works for each per-frame mapid. | A timer in the time-series hook that re-mints ahead of expiry. |
| No `month` bucket for the slider | Per the design decision; per-scene is the only mode. | A frontend radio in the Sidebar. |
| No `leaflet-compare` plugin | The swipe uses pure CSS `clip-path`; no new dep. | If the user wants a magnifier / spyglass later, add the plugin then. |
| Timelapse is still a GIF (not MP4) | Locked per the design's user decision. | A content-type sniff + `<video>` tag instead of `<a download>`. |
| Compare uses single slot A = current frame; slot B = any other | A more flexible "compare any two arbitrary frames" UI is [LATER]. | Multi-frame compare for the time series. |

## What's next

**Phase 3 — Spectral extension + export.** Broader spectral products;
GeoTIFF/PNG export via async GEE `getDownloadURL`; `ExportPanel` returns.
See the [roadmap](./docs/superpowers/specs/2026-07-23-orbiter-fusion-roadmap.md)
for the full list.

## Provenance

The Phase 2 design was a single-expert pass grounded in the live tree
(Phase 0 + Phase 1 are both complete; Phase 2 is purely additive). The
four design open questions were resolved with the recommended defaults:

- **Per-date mapid**: loop the existing `/api/fusion/gee-harmonize` (no new endpoint).
- **Date buckets**: per-scene.
- **Compare UI**: swipe (CSS `clip-path` + draggable divider).
- **Timelapse**: re-add Sidebar control, keep the existing GIF endpoint.
