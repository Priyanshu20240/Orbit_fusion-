// src/hooks/useFusion.js
//
// The race-safe GEE-fusion dispatch. Extracted from App.jsx so the
// click-race test (M8b) can drive it in isolation without a full
// `<App />` render. The hook returns the current `status` (loading /
// success / empty / error) and the active layer; the host component
// dispatches the resulting layer into the store via the `onLayer` callback.
//
// AbortController logic (M8b spec, design §C.3.4):
//   - One ref, ctrlRef, holds the in-flight controller.
//   - Each run aborts the previous one before starting.
//   - A `stale-winner guard` checks `signal.aborted` after the response
//     returns so the slow NDVI doesn't overwrite the fast true_color.
//   - The hook also aborts on unmount.

import { useCallback, useEffect, useRef, useState } from "react";
import { request, humanize } from "../api/client.js";

export function useFusion({ aoi, dateRange, activeSatellites, dispatch, onLayer, onStatusChange }) {
    const [status, setStatus] = useState("idle");
    const [error, setError] = useState(null);
    const [layer, setLayer] = useState(null);
    const ctrlRef = useRef(null);

    const onLayerRef = useRef(onLayer);
    useEffect(() => { onLayerRef.current = onLayer; }, [onLayer]);

    const onStatusChangeRef = useRef(onStatusChange);
    useEffect(() => { onStatusChangeRef.current = onStatusChange; }, [onStatusChange]);

    const setS = useCallback(
        (s, err = null) => {
            setStatus(s);
            setError(err);
            onStatusChangeRef.current?.(s, err);
        },
        []
    );

    const run = useCallback(
        async (visualization) => {
            if (!aoi) {
                setS("error", "Please draw an Area of Interest on the map first.");
                dispatch?.({ type: "FUSION_FAILED", error: "Please draw an Area of Interest on the map first." });
                return;
            }
            const platforms = Object.keys(activeSatellites).filter(
                (k) => activeSatellites[k] && ["sentinel", "landsat"].includes(k)
            );
            if (platforms.length === 0) {
                setS("error", "Please select at least one satellite.");
                dispatch?.({ type: "FUSION_FAILED", error: "Please select at least one satellite." });
                return;
            }

            // Cancel any in-flight fusion.
            ctrlRef.current?.abort();
            const ctrl = new AbortController();
            ctrlRef.current = ctrl;
            setS("loading");
            dispatch?.({ type: "FUSION_STARTED", visualization });

            const min_lon = aoi.min_lon ?? (typeof aoi.bounds?.getWest === "function" ? aoi.bounds.getWest() : aoi.west);
            const min_lat = aoi.min_lat ?? (typeof aoi.bounds?.getSouth === "function" ? aoi.bounds.getSouth() : aoi.south);
            const max_lon = aoi.max_lon ?? (typeof aoi.bounds?.getEast === "function" ? aoi.bounds.getEast() : aoi.east);
            const max_lat = aoi.max_lat ?? (typeof aoi.bounds?.getNorth === "function" ? aoi.bounds.getNorth() : aoi.north);

            try {
                const result = await request("/api/fusion/gee-harmonize", {
                    body: {
                        bounds: [min_lon, min_lat, max_lon, max_lat],
                        geojson: aoi.geojson,
                        start_date: dateRange.startDate,
                        end_date: dateRange.endDate,
                        cloud_cover: 20,
                        visualization,
                        platforms,
                    },
                    signal: ctrl.signal,
                });
                // Stale-winner guard: a newer run aborted us.
                if (ctrl.signal.aborted) return;

                const layerObj = {
                    id: `gee-fusion-${result.fusion_id}`,
                    idPrefix: "gee-fusion-",
                    name: `🛰️ GEE Fusion (${visualization})`,
                    satellite: "fusion",
                    kind: "gee",
                    mode: visualization,
                    tileUrl: result.tile_url_template,
                    fusionId: result.fusion_id,
                    expiresAt: result.expires_at,
                    bounds: result.bounds,
                    maxNativeZoom: result.max_native_zoom ?? 14,
                    visible: true,
                    opacity: 100,
                };
                setLayer(layerObj);
                onLayerRef.current?.(layerObj);
                dispatch?.({ type: "LAYER_ADDED", layer: layerObj });
                dispatch?.({ type: "FUSION_SUCCEEDED" });

                const total = (result.scene_counts?.sentinel || 0) + (result.scene_counts?.landsat || 0);
                if (total === 0) {
                    setS("empty");
                } else {
                    setS("success");
                }
            } catch (err) {
                if (err.name === "AbortError") return; // superseded click — silent
                const errMsg = humanize(err);
                setS("error", errMsg);
                dispatch?.({ type: "FUSION_FAILED", error: errMsg });
            }
        },
        [aoi, dateRange, activeSatellites, dispatch, setS]
    );

    // Abort on unmount.
    useEffect(() => () => ctrlRef.current?.abort(), []);

    return { run, status, error, layer };
}
