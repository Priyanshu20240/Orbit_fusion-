// src/hooks/useTimeSeries.js
//
// Phase 2 — per-scene time series for the TimeSlider.
//
// What this hook owns:
//   1. The POST /api/scenes/overlap fetch that produces the per-scene list.
//   2. The per-frame loop that mints a FusionMapResponse per (date, mode)
//      by calling the existing POST /api/fusion/gee-harmonize with
//      start_date == end_date == frame.date (one-day window).
//   3. The AbortController that cancels the in-flight loop when a new
//      dispatch lands (new search, date range change, AOI change, manual
//      TIME_SERIES_CLEAR) — same pattern as useFusion.js (M8b).
//   4. The TIME_SERIES_SET_CURRENT dispatch when the slider moves, which
//      the reducer (see state/reducer.js) maps to a `LAYER_UPDATED` on the
//      existing active layer. **The data-testid="layer-${mode}" container
//      is stable across slider swaps** — this is the M8b click-race
//      invariant extended to the slider.
//
// What this hook does NOT own:
//   - The active layer's lifecycle (LAYER_ADDED/REMOVED). That's useFusion.
//   - The compare slotB layer. That's a peer L.tileLayer managed by
//     SwipeCompare.jsx (Phase 2 §C.5).
//   - The TimeSlider UI. That's components/TimeSlider.jsx (M4).

import { useCallback, useEffect, useRef } from "react";
import { request, humanize } from "../api/client.js";
import {
    TIME_SERIES_REQUESTED,
    TIME_SERIES_FRAMES_LOADED,
    TIME_SERIES_FRAME_READY,
    TIME_SERIES_FAILED,
    TIME_SERIES_SET_CURRENT,
    TIME_SERIES_CLEAR,
} from "../state/actions.js";

/** Per-request default — the cap the backend's /api/scenes/overlap honors. */
const DEFAULT_MAX_FRAMES = 50;
/** Concurrency cap for the per-frame loop. */
const DEFAULT_CONCURRENCY = 4;

function dayWindow(dateStr) {
    return { startDate: dateStr, endDate: dateStr };
}

export function useTimeSeries({
    aoi,
    dateRange,
    activeSatellites,
    visualization,
    dispatch,
    maxFrames = DEFAULT_MAX_FRAMES,
    concurrency = DEFAULT_CONCURRENCY,
}) {
    // One ref for the in-flight overlap fetch + per-frame loop.
    // Any new run aborts the previous one.
    const ctrlRef = useRef(null);
    // Track the key under which a fetch was started so we can detect
    // stale dispatches after a clear.
    const runIdRef = useRef(0);

    const abort = useCallback(() => {
        ctrlRef.current?.abort();
        ctrlRef.current = null;
    }, []);

    // ── The main run() — fires the overlap fetch + the per-frame loop. ──
    const run = useCallback(async () => {
        if (!aoi) {
            return;
        }
        const platforms = Object.keys(activeSatellites || {}).filter(
            (k) => activeSatellites[k] && (k === "sentinel" || k === "landsat")
        );
        if (platforms.length === 0) return;

        abort();
        const ctrl = new AbortController();
        ctrlRef.current = ctrl;
        const myRunId = ++runIdRef.current;

        dispatch({ type: TIME_SERIES_REQUESTED });

        let frames = [];
        try {
            // 1) Overlap fetch — per-scene date list for the (aoi, date_range, platforms).
            const overlap = await request("/api/scenes/overlap", {
                body: {
                    bbox: {
                        min_lon: aoi.min_lon, min_lat: aoi.min_lat,
                        max_lon: aoi.max_lon, max_lat: aoi.max_lat,
                    },
                    start_date: dateRange.startDate,
                    end_date: dateRange.endDate,
                    max_cloud_cover: 30,
                    limit: maxFrames,
                },
                signal: ctrl.signal,
            });
            if (ctrl.signal.aborted) return;
            frames = (overlap?.frames ?? []).slice(0, maxFrames);
            dispatch({
                type: TIME_SERIES_FRAMES_LOADED,
                window: { startDate: dateRange.startDate, endDate: dateRange.endDate },
                frames: frames.map((f) => ({
                    date: f.date,
                    sensor: f.sensor,
                    ready: false,
                    fusionId: null,
                    tileUrl: null,
                    sceneCounts: null,
                })),
            });
        } catch (err) {
            if (err?.name === "AbortError") return;
            if (myRunId !== runIdRef.current) return; // superseded
            dispatch({ type: TIME_SERIES_FAILED, error: humanize(err) || "Time series failed" });
            return;
        }

        if (frames.length === 0) {
            return; // empty window; reducer will reflect frames=[].
        }

        // 2) Per-frame loop. Concurrency cap; per-frame abort via the same
        //    controller so a clear / re-run can short-circuit the rest.
        const queue = frames.slice();
        const inFlight = new Set();
        const dispatchFrameReady = (date, sensor, fusionId, tileUrl, sceneCounts) => {
            if (myRunId !== runIdRef.current) return; // superseded
            if (ctrl.signal.aborted) return;
            dispatch({
                type: TIME_SERIES_FRAME_READY,
                date, sensor, fusionId, tileUrl, sceneCounts,
            });
        };

        const fetchOne = async (frame) => {
            const win = dayWindow(frame.date);
            try {
                const r = await request("/api/fusion/gee-harmonize", {
                    body: {
                        bounds: [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat],
                        start_date: win.startDate,
                        end_date: win.endDate,
                        cloud_cover: 30,
                        visualization,
                        platforms,
                    },
                    signal: ctrl.signal,
                });
                if (ctrl.signal.aborted) return;
                dispatchFrameReady(
                    frame.date,
                    frame.sensor,
                    r.fusion_id,
                    r.tile_url_template,
                    r.scene_counts,
                );
            } catch (err) {
                if (err?.name === "AbortError") return;
                // Per-frame errors are non-fatal — leave the frame in
                // `ready: false` so the slider can show an empty tick.
                // The reducer doesn't need a per-frame FAILED action;
                // the user can re-run by re-dispatching the search.
                // (We deliberately do not dispatch TIME_SERIES_FAILED
                //  for a single frame failure.)
            }
        };

        const pump = async () => {
            while (queue.length > 0 && inFlight.size < concurrency && !ctrl.signal.aborted) {
                const frame = queue.shift();
                const p = fetchOne(frame);
                inFlight.add(p);
                p.finally(() => inFlight.delete(p));
            }
        };
        // Fill the initial pool, then refill on each settle.
        while (queue.length > 0 && !ctrl.signal.aborted) {
            await pump();
            if (inFlight.size === 0) break;
            await Promise.race(inFlight);
        }
    }, [aoi, dateRange, activeSatellites, visualization, dispatch, maxFrames, concurrency, abort]);

    // Auto-run when aoi / date range / platforms / viz change. We re-fire
    // unconditionally — AOI_CHANGED + DATE_RANGE_CHANGED dispatch
    // TIME_SERIES_CLEAR first (the reducer does this), so the new run
    // sees an empty `frames` and refills cleanly.
    useEffect(() => {
        if (!aoi) return;
        run();
        return () => abort();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [aoi, dateRange?.startDate, dateRange?.endDate, activeSatellites?.sentinel, activeSatellites?.landsat, visualization]);

    // Abort on unmount.
    useEffect(() => () => abort(), [abort]);

    // ── Slider actions ─────────────────────────────────────────────────
    const setCurrent = useCallback((idx) => {
        dispatch({ type: TIME_SERIES_SET_CURRENT, idx });
    }, [dispatch]);

    const clear = useCallback(() => {
        abort();
        dispatch({ type: TIME_SERIES_CLEAR });
    }, [abort, dispatch]);

    return { run, setCurrent, clear };
}
