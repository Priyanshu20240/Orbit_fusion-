// src/hooks/useTimelapse.js
//
// Phase 2 (M6) — re-plumb the existing /api/fusion/timelapse endpoint into
// a real UI control. The endpoint has been kept since Phase 0 (M5 re-plumbed
// it through the strategy registry) but had no UI; this hook + the Sidebar
// button close the loop.

import { useCallback, useEffect, useRef } from "react";
import { request, humanize } from "../api/client.js";
import { TIMELAPSE_STARTED, TIMELAPSE_SUCCEEDED, TIMELAPSE_FAILED } from "../state/actions.js";

/**
 * @param {object} args
 * @param {object|null} args.aoi - { min_lon, min_lat, max_lon, max_lat, geojson? }
 * @param {object} args.dateRange - { startDate, endDate }
 * @param {object} args.activeSatellites - { sentinel, landsat, bhuvan }
 * @param {string} args.visualization - selected visualization id
 * @param {Function} args.dispatch
 */
export function useTimelapse({ aoi, dateRange, activeSatellites, visualization, dispatch }) {
    const ctrlRef = useRef(null);
    const abort = useCallback(() => {
        ctrlRef.current?.abort();
        ctrlRef.current = null;
    }, []);

    const run = useCallback(async () => {
        if (!aoi) return;
        // Pick a platform — default to "sentinel" (the cheaper one).
        // The endpoint takes a single `platform`, not a list; we pick the
        // first enabled of [sentinel, landsat].
        const platform = activeSatellites?.sentinel
            ? "sentinel"
            : activeSatellites?.landsat
                ? "landsat"
                : "sentinel";

        abort();
        const ctrl = new AbortController();
        ctrlRef.current = ctrl;
        dispatch({ type: TIMELAPSE_STARTED });

        try {
            const r = await request("/api/fusion/timelapse", {
                body: {
                    bounds: [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat],
                    start_date: dateRange.startDate,
                    end_date: dateRange.endDate,
                    platform,
                    visualization,
                    geojson: aoi.geojson ?? null,
                },
                signal: ctrl.signal,
            });
            if (ctrl.signal.aborted) return;
            if (r?.success && r.url) {
                dispatch({ type: TIMELAPSE_SUCCEEDED, url: r.url, count: r.count ?? 0 });
            } else {
                const msg = r?.error || "Timelapse generation failed";
                dispatch({ type: TIMELAPSE_FAILED, error: msg });
            }
        } catch (err) {
            if (err?.name === "AbortError") return;
            dispatch({ type: TIMELAPSE_FAILED, error: humanize(err) || "Timelapse failed" });
        }
    }, [aoi, dateRange, activeSatellites, visualization, dispatch, abort]);

    useEffect(() => () => abort(), [abort]);
    return { run };
}
