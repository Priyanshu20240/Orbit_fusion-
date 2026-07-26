// src/state/AppStore.jsx
//
// Two contexts over one reducer. The split (Settings vs Layers) is the
// design §C.3.1 insight: opacity drags fire on the layers context, so the
// Sidebar (which subscribes to Settings) doesn't re-render.
//
// useSettings() and useLayers() expose typed accessors. useDispatch()
// returns the store's dispatch; components dispatch plain action objects
// (see state/actions.js).

import React, { createContext, useContext, useReducer, useMemo, useEffect } from "react";
import { reducer, initialState } from "./reducer.js";

const SettingsContext = createContext(null);
const LayersContext = createContext(null);
const DispatchContext = createContext(null);

export function AppStoreProvider({ children }) {
    const [state, dispatch] = useReducer(reducer, initialState);

    // The Settings vs Layers split is implemented via two memoised
    // sub-objects of the same state. This is the standard reducer+context
    // pattern, not Redux.
    const settings = useMemo(
        () => ({
            aoi: state.aoi,
            dateRange: state.dateRange,
            activeSatellites: state.activeSatellites,
            selectedVisualization: state.selectedVisualization,
            basemapId: state.basemapId,
            searchResults: state.searchResults,
            isSearching: state.isSearching,
            searchError: state.searchError,
            selectedScene: state.selectedScene,
            mapCenter: state.mapCenter,
        }),
        [
            state.aoi,
            state.dateRange,
            state.activeSatellites,
            state.selectedVisualization,
            state.basemapId,
            state.searchResults,
            state.isSearching,
            state.searchError,
            state.selectedScene,
            state.mapCenter,
        ]
    );
    const layers = useMemo(
        () => ({
            layers: state.layers,
            isProcessingFusion: state.isProcessingFusion,
            activeVisualization: state.activeVisualization,
            fusionError: state.fusionError,
            fusionEmpty: state.fusionEmpty,
            toasts: state.toasts,
            // Phase 2: time series + compare + timelapse slices.
            timeSeries: state.timeSeries,
            compare: state.compare,
            timelapse: state.timelapse,
        }),
        [
            state.layers,
            state.isProcessingFusion,
            state.activeVisualization,
            state.fusionError,
            state.fusionEmpty,
            state.toasts,
            state.timeSeries,
            state.compare,
            state.timelapse,
        ]
    );

    return (
        <DispatchContext.Provider value={dispatch}>
            <SettingsContext.Provider value={settings}>
                <LayersContext.Provider value={layers}>
                    {children}
                </LayersContext.Provider>
            </SettingsContext.Provider>
        </DispatchContext.Provider>
    );
}

export function useSettings() {
    const ctx = useContext(SettingsContext);
    if (!ctx) throw new Error("useSettings must be used within AppStoreProvider");
    return ctx;
}

export function useLayers() {
    const ctx = useContext(LayersContext);
    if (!ctx) throw new Error("useLayers must be used within AppStoreProvider");
    return ctx;
}

export function useDispatch() {
    const ctx = useContext(DispatchContext);
    if (!ctx) throw new Error("useDispatch must be used within AppStoreProvider");
    return ctx;
}

/** Convenience: returns a stable action dispatcher for a given AOI. */
export function useAoiActions() {
    const dispatch = useDispatch();
    return {
        setAoi: (input) => {
            if (!input) {
                dispatch({ type: "AOI_CHANGED", aoi: null });
                return;
            }
            const bounds = input.bounds || input;
            dispatch({
                type: "AOI_CHANGED",
                aoi: {
                    min_lon: typeof bounds.getWest === "function" ? bounds.getWest() : bounds.min_lon ?? bounds[0],
                    min_lat: typeof bounds.getSouth === "function" ? bounds.getSouth() : bounds.min_lat ?? bounds[1],
                    max_lon: typeof bounds.getEast === "function" ? bounds.getEast() : bounds.max_lon ?? bounds[2],
                    max_lat: typeof bounds.getNorth === "function" ? bounds.getNorth() : bounds.max_lat ?? bounds[3],
                    geojson: input.geojson ?? null,
                },
            });
        },
    };
}
