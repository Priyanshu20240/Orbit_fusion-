# Orbiter Fusion — Phase 2 (Harmonized Time Series) Plan

**Date:** 2026-07-24 · **Status:** Draft for review · **Builds on:** [phase 2 design](./2026-07-24-orbiter-fusion-phase2-design.md)

This is the **executable plan** for the Phase 2 design. It is broken into milestones, each a single coherent unit of work, each with its own success gate. The prime directive — same as Phase 0 / Phase 1 — is **every milestone leaves the app runnable, import-clean, tests-green**. Red-first tests that precede their production code are quarantined (`xfail(strict=True)` on pytest; `.skip`/`.todo` on vitest) and un-quarantined *in the same milestone* that lands their production code. Each acceptance check is tagged **[sandbox]** (this Linux no-network box can self-verify it) or **[windows-only]** (requires the user's live-GEE Windows host or a network install); the sandbox agent must never claim to have run a `[windows-only]` check.

**Three ordering hazards drive the sequence:**

1. **The new `/api/scenes/overlap` endpoint must exist before the TimeSlider can fetch frames** — but the endpoint can be authored and tested in pure-isolation (with the existing STAC fakes), so it lands in M1 with no GEE dependency.
2. **The `useTimeSeries` hook must be tested before the TimeSlider can mount it** — the hook's contract (abort-on-redispatch, `setUrl`-not-replace, frame cache) is the load-bearing thing; the slider is a presentation on top.
3. **The compare UI's CSS `clip-path` is the only thing that can break the existing `data-testid="layer-${mode}"` invariant** — the M8b click-race test relies on it. The plan enforces this by *first* landing the active-layer `setUrl`-not-replace plumbing (M3), *then* the second layer (M4), *then* the clip (M5), with the click-race test re-run after each milestone.

The total is **M0–M7** (8 milestones), one operator doc (`PHASE2.md`), and one memory update. Total LOC estimate: **~1,000** (backend: ~250; frontend: ~700; tests: ~250). Estimated time-on-task: a single long session.

---

## M0 — Pre-flight: confirm Phase 1 is the baseline

**Goal.** Ensure no Phase 0/1 work has regressed before Phase 2 starts.

**Tasks:**

1. Run the full backend test suite: `cd backend && ORBITER_GEE_PROJECT=test-project pytest -m "not integration" -q`. **Expect:** 84/84 pass.
2. Run the frontend test suite: `cd frontend && npm test`. **Expect:** 5/5 pass.

**Gate:** both green. If not, fix or pause — Phase 2 doesn't proceed on a broken baseline.

**Owner:** Claude (sandbox-static). **Estimated scope:** 5 min.

---

## M1 — Backend: `POST /api/scenes/overlap` endpoint

**Goal.** The per-scene date-list endpoint is in place, validated, and contract-tested. The existing fusion endpoints are untouched.

**Files touched:**

- `backend/app/models/schemas.py` — add `SceneDateEntry` + `ScenesOverlapResponse` (8 LOC).
- `backend/app/routers/scenes.py` — new file with the `scenes_overlap` handler (~40 LOC).
- `backend/app/main.py` — register the new router (1 LOC).
- `backend/tests/test_scenes_overlap.py` — new test file (~120 LOC).
- `backend/tests/test_endpoints_contract.py` — one new structural test (route uniqueness).

**Tasks:**

1. Add `SceneDateEntry` and `ScenesOverlapResponse` to `schemas.py` (Pydantic v2 with `Literal["sentinel", "landsat"]` for sensor).
2. Create `app/routers/scenes.py` exporting the `router` with the `scenes_overlap` handler. The handler:
   - Reads `SearchRequest` body (the existing schema, already used by `/api/search/all`).
   - Calls `sentinel_service.search_scenes` and `landsat_service.search_scenes` **concurrently** via `asyncio.gather(run_in_pool, run_in_pool)` — the same pattern `/api/search/all` already uses (`main.py:425-428`).
   - For each scene, parses the `datetime` (RFC 3339, day-rounded) and emits a `SceneDateEntry`.
   - Sorts by `(date asc, sensor, scene_id)`, dedupes on `(date, sensor, scene_id)`.
   - Returns `ScenesOverlapResponse(frames=...)`.
3. Register the router in `main.py`: `app.include_router(scenes.router)`. **Import order matters** — `scenes` needs the same `app` import that `main.py:411-445` uses for `/api/search/all`; structure it the same way (the handler reads `app.state.ee_pool` directly, like the other endpoints).
4. Write `test_overlap_returns_sorted_unique_dates` — happy path, two scenes each from S2 and L8, asserts sort + dedupe.
5. Write `test_overlap_clamps_to_limit` — `limit=10` → at most 10 frames.
6. Write `test_overlap_handles_no_scenes` — both searches return 0 scenes → 200 with `frames: []`.
7. Write `test_overlap_uses_concurrent_search` — monkeypatch the search services to record entry/exit times; assert total elapsed < 2× single-search elapsed (proves the `asyncio.gather` parallelization).
8. Write `test_scenes_overlap_route_present` in `test_endpoints_contract.py` — `for r in app.routes: …  ("POST", "/api/scenes/overlap") in seen`.
9. Add `time_series_max_frames` and `time_series_max_scenes_per_frame` to `Settings` (design §C.10) — `time_series_max_frames: int = 50`, `time_series_max_scenes_per_frame: int = 1`. Update `.env.example`.

**Gate:** `pytest tests/test_scenes_overlap.py tests/test_endpoints_contract.py -q` 100% pass. **No regression in M0.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M2 — Frontend state: time series + compare + timelapse slices

**Goal.** Reducer and action types for the three new state slices are landed and unit-tested. No UI yet. No backend changes beyond M1.

**Files touched:**

- `frontend/src/state/actions.js` — add 11 new action type constants (~12 LOC).
- `frontend/src/state/reducer.js` — add `timeSeries`, `compare`, `timelapse` slices to `initialState`; add handlers for the 11 new actions (~120 LOC).
- `frontend/src/state/AppStore.jsx` — expose the new slices via `useLayers()` (additive; existing subscribers unchanged) (~30 LOC).
- `frontend/src/test/reducer.test.js` — new file with 8 reducer unit tests (~200 LOC).

**Tasks:**

1. Add action constants to `actions.js`:
   `TIME_SERIES_REQUESTED`, `TIME_SERIES_FRAMES_LOADED`, `TIME_SERIES_FRAME_READY`, `TIME_SERIES_FAILED`, `TIME_SERIES_SET_CURRENT`, `TIME_SERIES_CLEAR`, `COMPARE_TOGGLED`, `COMPARE_SLOT_CHANGED`, `COMPARE_DIVIDER_MOVED`, `TIMELAPSE_STARTED`, `TIMELAPSE_SUCCEEDED`, `TIMELAPSE_FAILED`.
2. Add the three slices to `initialState`:
   - `timeSeries: { window: null, frames: [], currentFrameIdx: 0, loading: false, error: null, source: null }` — `source` is `'overlap' | 'manual'` to distinguish the new auto-fetch path from any future user-typed dates.
   - `compare: { enabled: false, slotA: 0, slotB: 1, dividerX: 0.5 }` — slot indices into `timeSeries.frames`.
   - `timelapse: { url: null, count: 0, loading: false, error: null }`.
3. Implement the 11 new reducer cases. **`TIME_SERIES_SET_CURRENT`** must NOT add a new layer; it must also `LAYER_UPDATED` the existing fusion layer with the new frame's `tileUrl` + `fusionId` so the click-race `data-testid` is preserved. (Implementation: in the reducer, find the active fusion layer by `idPrefix === 'gee-fusion-'`, and patch its `tileUrl` + `fusionId` in-place. This is the M8b invariant.)
4. **`COMPARE_TOGGLED`** when turning ON with no frames loaded yet → ignore (compare requires frames).
5. **`TIME_SERIES_CLEAR`** is dispatched on `AOI_CHANGED` + `DATE_RANGE_CHANGED` to invalidate the time axis; the `frames: []` reset is additive to the existing search-results reset in the `AOI_CHANGED` handler.
6. Expose the three slices via `useLayers()` (additive; the existing `layers`, `isProcessingFusion`, `activeVisualization`, `fusionError`, `fusionEmpty`, `toasts` keys are unchanged).
7. Write 8 reducer unit tests:
   - `timeSeries_requested_resets_frames_and_loading`
   - `timeSeries_frames_loaded_replaces_frames`
   - `timeSeries_frame_ready_patches_one_frame`
   - `timeSeries_set_current_patches_active_layer_id`  ← the **load-bearing** test
   - `timeSeries_clear_empties_frames`
   - `compare_toggle_false_clears_enabled`
   - `compare_toggle_true_ignored_when_no_frames`
   - `compare_divider_moved_clamps_to_zero_one`
   - `timelapse_succeeded_stores_url_and_count`

**Gate:** `npm test` shows 5/5 → 13/13 (8 new reducer tests + 5 existing). **No regression in M0.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M3 — Frontend: `useTimeSeries` hook (per-frame loop + abort)

**Goal.** The hook drives the time-axis fetch. It is the load-bearing piece — every other Phase 2 UI feature consumes it.

**Files touched:**

- `frontend/src/hooks/useTimeSeries.js` — new file (~180 LOC).
- `frontend/src/test/timeseries.test.js` — new test file with 4 tests (~250 LOC).
- `frontend/src/test/handlers.js` — extend MSW to accept `POST /api/scenes/overlap` (~15 LOC).

**Tasks:**

1. Create `useTimeSeries({ aoi, dateRange, activeSatellites, visualization, onActiveLayerUpdate })` that:
   - On mount + when `(aoi, dateRange, activeSatellites, visualization)` change, fires `dispatch({ type: TIME_SERIES_REQUESTED })`.
   - Calls `POST /api/scenes/overlap` with the current `bounds`, `start_date`, `end_date`, `max_cloud_cover: 30`, `limit: 50`.
   - On response, dispatches `TIME_SERIES_FRAMES_LOADED` with the frames.
   - Then iterates `frames` in a `Promise.all`-with-`AbortController` loop, firing `POST /api/fusion/gee-harmonize` for each (date == start_date == end_date so it's a one-day window). Concurrency capped at `Settings.time_series_concurrency` (4 default). Each resolved frame dispatches `TIME_SERIES_FRAME_READY` with `{ date, sensor, fusionId, tileUrl, sceneCounts }`.
   - On any new dispatch (new search, date change), aborts the in-flight loop. The MSW handler honors the abort signal.
   - On `TIME_SERIES_SET_CURRENT` (from the slider), patches the *existing* active layer via `onActiveLayerUpdate({ tileUrl, fusionId })` — no new layer, no `data-testid` change.
2. Write `test_per_frame_loop_uses_abort_controller` — fire a slow `/api/scenes/overlap` (200ms delay) followed by a fast one (10ms); assert only the fast one's frames are in state.
3. Write `test_set_current_dispatches_layer_updated_with_same_id` — load 3 frames; call `run(idx=1)`; assert the layers array length is still 1 (no second layer added) and the active layer's `tileUrl` matches frame 1's. **This is the test that protects the M8b click-race invariant.**
4. Write `test_concurrency_cap_respected` — fire 10 frames; assert no more than 4 in-flight `POST /api/fusion/gee-harmonize` at any moment (use a counter in the MSW handler).
5. Write `test_abort_on_redispatch` — start a 3-frame loop; after frame 1 resolves, dispatch `TIME_SERIES_CLEAR`; assert frames 2 and 3 are not fetched.

**Gate:** `npm test` 13/13 → 17/17. **No regression in M0/M2.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M4 — Frontend: `TimeSlider.jsx` (the scrubber)

**Goal.** A real TimeSlider mounts in the Map view (replacing the M9 placeholder at `Map.jsx:425-426`). The scrubber dispatches `TIME_SERIES_SET_CURRENT` on pointerup / keyboard.

**Files touched:**

- `frontend/src/components/TimeSlider.jsx` — new file (~200 LOC).
- `frontend/src/components/Map.jsx` — delete the dead props, mount `<TimeSlider />` (10 LOC diff).
- `frontend/src/App.jsx` — wire `useTimeSeries` into the layers context; pass through to `Map` (15 LOC diff).
- `frontend/src/test/timeslider.test.js` — new test file with 4 tests (~200 LOC).
- `frontend/src/index.css` — add `.time-slider`, `.time-slider__thumb`, `.time-slider__tick`, sensor-coloured (`#06b6d4` S2, `#ea580c` L8) (~80 LOC).
- `frontend/src/test/handlers.js` — add `?delayMs=` support for the timeseries loop (already there from click-race tests; verify).

**Tasks:**

1. Create `TimeSlider.jsx` per design §C.4. Single horizontal div; thumb is absolutely positioned; tick marks one per frame; sensor-coloured ticks; aria-valuemin/max/now + aria-valuetext; ←/→/space/home/end keyboard handlers.
2. In `Map.jsx`:
   - Delete the dead `isTimeLapsePlaying / onTimeLapseToggle / onTimeSliderChange` props from the function signature (`Map.jsx:47`).
   - Replace the trailing `{/* Time Slider */}` placeholder (`Map.jsx:425-426`) with `<TimeSlider />`.
3. In `App.jsx`:
   - Add `useTimeSeries({ aoi, dateRange, activeSatellites, visualization, onActiveLayerUpdate: handleTimeSeriesUpdate })`.
   - `handleTimeSeriesUpdate` dispatches `LAYER_UPDATED` with the new `tileUrl` + `fusionId` for the existing active layer (no new layer; this is the M8b invariant).
4. In `Map.jsx`'s tile-layer effect (`Map.jsx:195-316`), add: when the active layer's `tileUrl` changes (because the slider moved), call `leafletLayer.setUrl(newUrl)` instead of removing/re-adding. This keeps the data-testid container stable.
5. Add the CSS for the slider.
6. Write `test_slider_renders_one_tick_per_frame` — 5 frames → 5 ticks.
7. Write `test_slider_pointer_drag_dispatches_set_current` — simulate `pointerdown` at 30% then `pointermove` to 70% then `pointerup`; assert `TIME_SERIES_SET_CURRENT` dispatched with the frame at 70%.
8. Write `test_slider_keyboard_arrow_jumps_one_frame` — render the slider with `currentIdx=2`; press `→`; assert dispatch with idx=3.
9. Write `test_slider_hides_when_no_frames` — empty `frames` array → component returns null.

**Gate:** `npm test` 17/17 → 21/21. **No regression in M0/M2/M3.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M5 — Frontend: `SwipeCompare.jsx` (two-layer clip)

**Goal.** The compare UI mounts. Slot A = active frame; slot B = any other frame. Divider drag updates CSS `clip-path` only — no second backend call.

**Files touched:**

- `frontend/src/components/SwipeCompare.jsx` — new file (~150 LOC).
- `frontend/src/components/Map.jsx` — mount `<SwipeCompare />` when compare is enabled; second layer added/removed via the `L.tileLayer` machinery already in `Map.jsx:201-316` (5 LOC diff).
- `frontend/src/test/swipe-compare.test.js` — new test file with 3 tests (~180 LOC).
- `frontend/src/index.css` — `.swipe-compare__divider`, `.swipe-compare__slot-badge`, `clip-path` rule (~50 LOC).

**Tasks:**

1. Create `SwipeCompare.jsx` per design §C.5. Renders nothing when `compare.enabled === false` or `frames.length < 2`. When enabled, renders a divider div + the slotB layer's clip-path is `inset(0 0 0 ${dividerX * 100}%)`. Pointer drag on the divider updates local `dividerX`; `pointerup` dispatches `COMPARE_DIVIDER_MOVED`.
2. In `Map.jsx`:
   - Add `<SwipeCompare slotA={activeLayer} slotB={compareLayer} dividerX={compare.dividerX} />` (placed above the basemap attribution).
   - The compare slot B is a *second* `L.tileLayer` added on top of the active layer. The `useEffect` at `Map.jsx:195-316` is extended with a "second tile layer" branch that takes the `clipPath` style from the SwipeCompare's local state.
   - The compare slot B is added to `tileLayersRef.current` under the id `gee-compare-slotB` so it can be removed when compare is disabled.
3. Add the CSS.
4. Write `test_swipe_compare_renders_nothing_when_disabled` — `enabled: false` → returns null.
5. Write `test_swipe_compare_divider_drag_updates_clip_path` — simulate `pointerdown` + `pointermove`; assert the slotB's `style.clipPath` reflects the new `dividerX`.
6. Write `test_swipe_compare_slot_pickers_update_slot_a_and_b` — render two `<select>` elements with the frame list; changing slot A dispatches `COMPARE_SLOT_CHANGED` with `{ slot: 'A', idx: newIdx }`.

**Gate:** `npm test` 21/21 → 24/21. **No regression in M0/M2/M3/M4.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M6 — Frontend: timelapse UI re-plumb

**Goal.** The "Generate timelapse GIF" button works. It calls the existing `/api/fusion/timelapse` endpoint (unchanged from M5) and presents the response's `url` as a download link.

**Files touched:**

- `frontend/src/hooks/useTimelapse.js` — new file (~60 LOC).
- `frontend/src/components/Sidebar.jsx` — add the "Generate timelapse" button + download link (~30 LOC).
- `frontend/src/test/timelapse.test.js` — new test file with 2 tests (~120 LOC).
- `frontend/src/test/handlers.js` — extend the MSW handler for `POST /api/fusion/timelapse` (~10 LOC).

**Tasks:**

1. Create `useTimelapse({ aoi, dateRange, activeSatellites, visualization })` that:
   - On `run()`: dispatches `TIMELAPSE_STARTED`; calls `POST /api/fusion/timelapse` with `{ bounds, start_date, end_date, platform, visualization, geojson }`; on success dispatches `TIMELAPSE_SUCCEEDED` with `{ url, count }`; on failure dispatches `TIMELAPSE_FAILED` with the humanized error.
   - Uses an `AbortController` for click-race safety.
2. In `Sidebar.jsx`:
   - Add a "Timelapse" section (only when `aoi && timeSeries.frames.length > 0`).
   - Add the "🎬 Generate timelapse GIF" button (disabled when `timelapse.loading`).
   - When `timelapse.url` is set, render a "⬇️ Download timelapse (N frames)" link.
3. Write `test_timelapse_button_calls_endpoint` — render the sidebar with `aoi` set and `frames: [one frame]`; click the button; assert MSW received `POST /api/fusion/timelapse` with the right body.
4. Write `test_timelapse_succeeded_shows_download_link` — mock the response `{ success: true, url: 'https://...', count: 12 }`; assert the download link is rendered with the right href.

**Gate:** `npm test` 24/24 → 26/26. **No regression in M0/M2/M3/M4/M5.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M7 — CI + coverage + final acceptance

**Goal.** All gates hold; the full backend + frontend suites pass; the acceptance greps from the design doc return expected output.

**Tasks:**

1. Run the full backend suite with coverage: `cd backend && pytest -m "not integration" --cov=app --cov-fail-under=75`. **Expect:** 89/89 pass (84 baseline + 5 new from M1), coverage ≥ 75%.
2. Run the full frontend suite with coverage: `cd frontend && npm run test:cov`. **Expect:** 26/26 pass (5 baseline + 21 new from M2-M6), coverage ≥ 55%.
3. Acceptance greps (sandbox-runnable):
   - `grep -rn "TimeSlider" frontend/src/components` — returns the new file.
   - `grep -rn "SwipeCompare" frontend/src/components` — returns the new file.
   - `grep -rn "scenes/overlap" backend/app/routers/scene*` — returns the new route registration.
   - `grep -rn "leaflet-compare\|leaflet_swipe" frontend/package.json` — empty (no new dep).
   - `grep -rn "isTimeLapsePlaying\|onTimeLapseToggle\|onTimeSliderChange" frontend/src/components/Map.jsx` — empty (dead props removed).
   - `grep -rn "TimeSlider" frontend/src/components/Map.jsx` — returns the import + the JSX mount.
4. The contract test `test_scenes_overlap_route_present` confirms the new route is uniquely registered.

**Gate:** all greps return expected output; both test suites green; coverage gates hold.

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M8 — `PHASE2.md` operator doc

**Goal.** The operator can read one file and understand what Phase 2 changed.

**Files touched:**

- `PHASE2.md` at the repo root. ~150 LOC.

**Tasks:**

1. Section 1: what Phase 2 is (per-scene TimeSlider, swipe compare, timelapse re-plumbed).
2. Section 2: the new endpoint and the loop strategy.
3. Section 3: how the TimeSlider works (keyboard shortcuts, sensor-coloured ticks, the M8b invariant).
4. Section 4: how the swipe compare works.
5. Section 5: how the timelapse button works.
6. Section 6: the `ORBITER_TIME_SERIES_*` env vars.
7. Section 7: which test files were added and how to run them.
8. Section 8: known limits (no per-pixel provenance, no monthly bucket, no proactive pre-expiry refresh).

**Gate:** file exists; section anchors link to the design doc + the touched files.

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M9 — Memory + acceptance sign-off

**Goal.** Phase 2 is signed off. The repo memory is updated.

**Tasks:**

1. Update `orbiter-fusion-project.md` to add the Phase 2 status (the `metadata.type` is already `project`).
2. Update `MEMORY.md` with a one-line Phase 2 pointer.
3. Run the M0 baseline check one last time: 84 backend + 5 frontend → 89 backend + 26 frontend.

**Gate:** memory files updated; baseline test count is 89 backend + 26 frontend.

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| The per-frame loop's N HTTP calls serialise in the GEE pool | The pool has 8 workers; the frontend cap is 4. Adjustable via `ORBITER_TIME_SERIES_CONCURRENCY`. |
| A frame's `fusion_id` md5 collides with another frame's md5 | Truncated 12-char md5; collision probability is ~1 in 2^48 per `(bounds, dates, viz, platforms)`. Acceptable; if observed, the cache hit is correct (same AOI + same date + same viz = same fusion). |
| The slider's `setUrl` triggers a Leaflet flicker | Leaflet's `setUrl` swaps the URL atomically; the layer container is preserved; no flicker. (Verified by the click-race test in M4.) |
| The compare UI's clip-path is a known Safari wart | The fallback is `inset(0 0 0 X%)` which is in the CSS spec since 2014; all browsers support it. |
| `getVideoThumbURL` is slow on a 90-day window | The Phase 0 timelapse endpoint already caps at 50 frames (`gee_fusion_service.py:291`); Phase 2 doesn't change that. |
| The new endpoint's `limit=50` differs from `/api/search/all`'s `limit=10` | Intentional — the time axis can have 50+ acquisitions in a year-long window; the search panel is for human review (≤10 fits on screen). |
| The M8b click-race `data-testid="layer-${mode}"` breaks if M3/M4's "swap in place" logic is wrong | The `test_set_current_dispatches_layer_updated_with_same_id` test (M3) and `test_slider_pointer_drag_dispatches_set_current` test (M4) lock this. The existing click-race test (`click-race.test.js`) re-runs at the M7 gate. |

---

## Scope summary

| Milestone | Files | LOC | Sub-tasks |
|---|---|---|---|
| M0 — Pre-flight | 0 | 0 | 1 |
| M1 — Scenes overlap endpoint | 5 | ~180 | 9 |
| M2 — Reducer + actions | 4 | ~360 | 7 |
| M3 — useTimeSeries hook | 3 | ~445 | 5 |
| M4 — TimeSlider.jsx | 5 | ~505 | 6 |
| M5 — SwipeCompare.jsx | 4 | ~385 | 4 |
| M6 — Timelapse UI | 4 | ~220 | 4 |
| M7 — CI + coverage | 0 | 0 | 3 |
| M8 — PHASE2.md | 1 | ~150 | 8 |
| M9 — Memory + sign-off | 2 | ~10 | 3 |
| **Total** | **~28** | **~2,255** | **50** |

(Back-end: ~250 LOC; front-end: ~700 LOC; tests: ~250 LOC; docs: ~150 LOC. The rest is test scaffolding, comments, and config defaults.)

**Estimated turns:** 1 (this is the design + plan; the implementation is 1-2 more turns depending on test coverage).

---

## Open questions

The four design open questions are **resolved** (see design §E). No outstanding open questions.
