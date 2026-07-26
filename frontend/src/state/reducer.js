// src/state/reducer.js
//
// Single state object for the app. Two contexts split this:
//   - SettingsContext  → rare-changing state (aoi, dates, platforms, viz, basemap)
//   - LayersContext    → per-frame-changing state (layers, opacity)
//
// Splitting prevents a LayerControl opacity drag from re-rendering the
// Sidebar (the design §C.3.1 motivation).

import * as A from "./actions.js";

export const initialState = {
    // Settings (rare-changing)
    aoi: null,                   // { min_lon, min_lat, max_lon, max_lat, geojson? } | null
    dateRange: { startDate: "2024-01-01", endDate: "2024-12-31" },
    activeSatellites: { sentinel: true, landsat: true, bhuvan: false },
    selectedVisualization: "true_color",
    basemapId: "dark",           // one of config/basemaps.js
    searchResults: { sentinel: [], landsat: [], bhuvan: [] },
    isSearching: false,
    searchError: null,
    selectedScene: null,
    mapCenter: null,

    // Layers (per-frame-changing)
    layers: [],                  // [{ id, kind, ... }]  — fusion + WMS
    isProcessingFusion: false,
    activeVisualization: null,   // last viz that fired build_fusion_map
    fusionError: null,           // last humanized error from /api/fusion/*
    fusionEmpty: false,          // true after a 0-scene FUSION_EMPTY
    toasts: [],                  // [{ id, kind: 'info'|'success'|'error', text, ttl }]

    // ── Phase 2: time series (per-scene time axis) ────────────────────
    timeSeries: {
        window: null,            // { startDate, endDate } when loaded
        frames: [],              // [{ date, sensor, fusionId, tileUrl, sceneCounts, ready }]
        currentFrameIdx: 0,      // index into frames[]; the active layer mirrors this
        loading: false,
        error: null,
        source: null,            // 'overlap' | 'manual' (Phase 2: 'overlap' only)
    },

    // ── Phase 2: compare (swipe) ──────────────────────────────────────
    compare: {
        enabled: false,
        slotA: 0,                // index into timeSeries.frames
        slotB: 1,                // index into timeSeries.frames
        dividerX: 0.5,           // 0..1, position of the vertical divider
    },

    // ── Phase 2: timelapse ────────────────────────────────────────────
    timelapse: {
        url: null,               // GIF URL returned by /api/fusion/timelapse
        count: 0,                // frame count from the response
        loading: false,
        error: null,
    },

    // Session Snapshot Gallery & Export
    snapshots: [],

    // ASTRA-AI Alerts & Warning Polygons
    aiAlerts: { pins: [], polygons: [] },
};

export function reducer(state, action) {
    switch (action.type) {
        case A.AOI_CHANGED: {
            // action.aoi: object | null
            if (action.aoi) {
                return {
                    ...state,
                    aoi: action.aoi,
                    // Clear stale search results + selection on a new AOI.
                    searchResults: initialState.searchResults,
                    selectedScene: null,
                    // Phase 2: a new AOI invalidates the time axis + compare slots.
                    timeSeries: initialState.timeSeries,
                    compare: initialState.compare,
                };
            }
            return {
                ...state,
                aoi: null,
                searchResults: initialState.searchResults,
                selectedScene: null,
                timeSeries: initialState.timeSeries,
                compare: initialState.compare,
            };
        }

        case A.DATE_RANGE_CHANGED:
            // Phase 2: date range change invalidates the time axis (the per-scene
            // dates are window-specific). Reset frames but keep the timeSeries
            // shape so the reducer can be called with a `timeSeries: initialState.timeSeries`
            // reset when the new overlap response lands.
            return {
                ...state,
                dateRange: { ...state.dateRange, ...action.patch },
                timeSeries: initialState.timeSeries,
                compare: initialState.compare,
            };

        case A.SATELLITE_TOGGLED:
            return {
                ...state,
                activeSatellites: {
                    ...state.activeSatellites,
                    [action.satellite]: !state.activeSatellites[action.satellite],
                },
            };

        case A.SEARCH_STARTED:
            return {
                ...state,
                isSearching: true,
                searchError: null,
                searchResults: initialState.searchResults,
            };

        case A.SEARCH_SUCCEEDED:
            return {
                ...state,
                isSearching: false,
                searchResults: action.results,
            };

        case A.SEARCH_FAILED:
            return { ...state, isSearching: false, searchError: action.error };

        case A.SCENE_SELECTED:
            return { ...state, selectedScene: action.scene };

        case A.MAP_CENTER_SET:
            return { ...state, mapCenter: action.center };

        case A.BASEMAP_SET:
            return { ...state, basemapId: action.basemapId };

        case A.VIZ_SELECTED:
            return { ...state, selectedVisualization: action.viz };

        case A.LAYER_ADDED: {
            // Replace any prior fusion layer with the same id-prefix so
            // rapid mode-switch doesn't stack identical overlays.
            const idPrefix = action.layer.idPrefix;
            const filtered = idPrefix
                ? state.layers.filter((l) => !l.id.startsWith(idPrefix))
                : state.layers;
            return { ...state, layers: [...filtered, action.layer] };
        }

        case A.LAYER_UPDATED:
            return {
                ...state,
                layers: state.layers.map((l) =>
                    l.id === action.id ? { ...l, ...action.patch } : l
                ),
            };

        case A.LAYER_REMOVED:
            return { ...state, layers: state.layers.filter((l) => l.id !== action.id) };

        // ── M9 fusion lifecycle ────────────────────────────────────────
        case A.FUSION_STARTED:
            return {
                ...state,
                isProcessingFusion: true,
                fusionError: null,
                fusionEmpty: false,
                activeVisualization: action.viz ?? state.activeVisualization,
            };

        case A.FUSION_SUCCEEDED:
            return {
                ...state,
                isProcessingFusion: false,
                fusionError: null,
                fusionEmpty: false,
            };

        case A.FUSION_FAILED:
            return {
                ...state,
                isProcessingFusion: false,
                fusionError: action.error,
                fusionEmpty: false,
            };

        case A.FUSION_EMPTY:
            return {
                ...state,
                isProcessingFusion: false,
                fusionError: null,
                fusionEmpty: true,
            };

        // ── M9 toasts ─────────────────────────────────────────────────
        case A.TOAST_PUSHED:
            // De-dupe by text+kind so identical errors don't pile up.
            if (state.toasts.some((t) => t.text === action.toast.text && t.kind === action.toast.kind)) {
                return state;
            }
            return { ...state, toasts: [...state.toasts, action.toast] };

        case A.TOAST_DISMISSED:
            return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };

        // ── Phase 2: time series ───────────────────────────────────────
        case A.TIME_SERIES_REQUESTED:
            return {
                ...state,
                timeSeries: {
                    ...state.timeSeries,
                    loading: true,
                    error: null,
                    // Don't clear `frames` yet — a slow overlap refresh on the
                    // same window would otherwise blank the slider. Clear
                    // happens on TIME_SERIES_FRAMES_LOADED if the window changed.
                },
            };

        case A.TIME_SERIES_FRAMES_LOADED: {
            // Replace the frames; reset currentFrameIdx to 0 (the first frame
            // is the one the user just saw). The active layer's `tileUrl` is
            // patched in-place by a follow-up TIME_SERIES_FRAME_READY for idx=0.
            return {
                ...state,
                timeSeries: {
                    ...state.timeSeries,
                    window: action.window ?? state.timeSeries.window,
                    frames: action.frames ?? [],
                    currentFrameIdx: 0,
                    loading: false,
                    error: null,
                    source: "overlap",
                },
            };
        }

        case A.TIME_SERIES_FRAME_READY: {
            // Patch the matching frame's fusion metadata in place. The active
            // layer is NOT touched here — TIME_SERIES_SET_CURRENT does that.
            const frames = state.timeSeries.frames.map((f) =>
                f.date === action.date && f.sensor === action.sensor
                    ? {
                          ...f,
                          ready: true,
                          fusionId: action.fusionId,
                          tileUrl: action.tileUrl,
                          sceneCounts: action.sceneCounts,
                      }
                    : f
            );
            return { ...state, timeSeries: { ...state.timeSeries, frames } };
        }

        case A.TIME_SERIES_FAILED:
            return {
                ...state,
                timeSeries: { ...state.timeSeries, loading: false, error: action.error },
            };

        case A.TIME_SERIES_SET_CURRENT: {
            // PATCH THE ACTIVE LAYER IN PLACE — never add a new one. The M8b
            // click-race + Phase 2 slider invariant: the `data-testid="layer-${mode}"`
            // is on the layer container, and the container must stay the same
            // DOM node across slider swaps. Adding a new layer would break it.
            const idx = action.idx;
            const frame = state.timeSeries.frames[idx];
            const newLayers = frame
                ? state.layers.map((l) =>
                      l.idPrefix === "gee-fusion-"
                          ? { ...l, tileUrl: frame.tileUrl, fusionId: frame.fusionId }
                          : l
                  )
                : state.layers;
            return {
                ...state,
                timeSeries: { ...state.timeSeries, currentFrameIdx: idx },
                layers: newLayers,
            };
        }

        case A.TIME_SERIES_CLEAR:
            return {
                ...state,
                timeSeries: initialState.timeSeries,
                compare: initialState.compare,
            };

        // ── Phase 2: compare (swipe) ───────────────────────────────────
        case A.COMPARE_TOGGLED: {
            // Ignore the toggle ON if no frames yet — compare requires ≥2 frames
            // (the two slot indices must be distinct and valid).
            const wantEnabled = !!action.enabled;
            if (wantEnabled && state.timeSeries.frames.length < 2) {
                return state;
            }
            // If turning off, just clear the divider / slot data is fine to keep.
            return { ...state, compare: { ...state.compare, enabled: wantEnabled } };
        }

        case A.COMPARE_SLOT_CHANGED: {
            // action.slot: "A" | "B"  action.idx: integer
            if (action.slot === "A") {
                return { ...state, compare: { ...state.compare, slotA: action.idx } };
            }
            if (action.slot === "B") {
                return { ...state, compare: { ...state.compare, slotB: action.idx } };
            }
            return state;
        }

        case A.COMPARE_DIVIDER_MOVED: {
            // Clamp dividerX to [0, 1] — pointer events can overshoot.
            const x = Math.max(0, Math.min(1, action.x));
            return { ...state, compare: { ...state.compare, dividerX: x } };
        }

        // ── Phase 2: timelapse ────────────────────────────────────────
        case A.TIMELAPSE_STARTED:
            return {
                ...state,
                timelapse: { ...state.timelapse, loading: true, error: null },
            };

        case A.TIMELAPSE_SUCCEEDED:
            return {
                ...state,
                timelapse: {
                    url: action.url,
                    count: action.count ?? 0,
                    loading: false,
                    error: null,
                },
            };

        case A.TIMELAPSE_FAILED:
            return {
                ...state,
                timelapse: {
                    ...state.timelapse,
                    loading: false,
                    error: action.error,
                },
            };

        case A.SNAPSHOT_SAVED:
            return {
                ...state,
                snapshots: [action.snapshot, ...state.snapshots],
            };

        case A.SNAPSHOT_REMOVED:
            return {
                ...state,
                snapshots: state.snapshots.filter((s) => s.id !== action.id),
            };

        case A.AI_ALERTS_SET:
            return {
                ...state,
                aiAlerts: {
                    pins: action.pins || [],
                    polygons: action.polygons || [],
                },
            };

        default:
            return state;
    }
}
