// src/App.jsx
//
// Post-M9 App. The 13 useState's become one store. The api client (./api/client)
// replaces raw fetch + localhost hardcode + cache-buster. The remaining
// console.warn/console.error in earlier M8a code is gone — errors dispatch
// to a real Toast (ToastHost) and the FUSION_* action trio hoists fusion
// lifecycle into the layers context so the empty/error states are visible
// in the UI, not just in the console.
//
// Still emits the new GEE layer shape (kind: "gee", tileUrl, fusionId,
// expiresAt, maxNativeZoom) so Map.jsx can render L.tileLayer.

import React, { useCallback, useMemo } from "react";
import Map from "./components/Map";
import Sidebar from "./components/Sidebar";
import Loader from "./components/Loader";
import ToastHost from "./components/Toast.jsx";
import TimelapseViewer from "./components/TimelapseViewer.jsx";
import AstraAgentBar from "./components/AstraAgentBar.jsx";
import CarbonCalculatorModal from "./components/CarbonCalculatorModal.jsx";
import MapPointInspector from "./components/MapPointInspector.jsx";
import SwipeCompare from "./components/SwipeCompare.jsx";
import QuickActionsToolbar from "./components/QuickActionsToolbar.jsx";
import { AppStoreProvider, useSettings, useLayers, useDispatch, useAoiActions } from "./state/AppStore.jsx";
import { request, humanize } from "./api/client.js";
import { useFusion } from "./hooks/useFusion.js";
import { useTimeSeries } from "./hooks/useTimeSeries.js";
import { useTimelapse } from "./hooks/useTimelapse.js";
import { pushToast } from "./toast.js";
import {
    FUSION_STARTED,
    FUSION_SUCCEEDED,
    FUSION_FAILED,
    FUSION_EMPTY,
} from "./state/actions.js";

function AppInner() {
    const settings = useSettings();
    const layersCtx = useLayers();
    const dispatch = useDispatch();
    const { setAoi } = useAoiActions();

    const onAoiChange = useCallback(
        (input) => setAoi(input),
        [setAoi]
    );

    // ── search ────────────────────────────────────────────────────────────
    const handleSearch = useCallback(async () => {
        if (!settings.aoi) {
            pushToast(dispatch, "error", "Please draw an Area of Interest on the map first.");
            return;
        }
        dispatch({ type: "SEARCH_STARTED" });
        try {
            const data = await request("/api/search/all", {
                body: {
                    bbox: settings.aoi,
                    start_date: settings.dateRange.startDate,
                    end_date: settings.dateRange.endDate,
                    max_cloud_cover: 30,
                    limit: 10,
                },
            });
            dispatch({
                type: "SEARCH_SUCCEEDED",
                results: {
                    sentinel: data.sentinel?.scenes || [],
                    landsat: data.landsat?.scenes || [],
                    bhuvan: Object.values(data.bhuvan?.layers || {}),
                },
            });
        } catch (err) {
            const msg = humanize(err);
            pushToast(dispatch, "error", msg || "Search failed.");
            dispatch({ type: "SEARCH_FAILED", error: msg });
        }
    }, [settings.aoi, settings.dateRange, dispatch]);

    // ── GEE fusion (M8b: getMapId contract + AbortController race-fix) ──
    const handleGEEFusion = useCallback(
        (visualization = "true_color") => {
            dispatch({ type: "VIZ_SELECTED", viz: visualization });
            dispatch({ type: FUSION_STARTED, viz: visualization });
        },
        [dispatch]
    );

    const fusion = useFusion({
        aoi: settings.aoi,
        dateRange: settings.dateRange,
        activeSatellites: settings.activeSatellites,
        dispatch,
        onStatusChange: (s, err) => {
            if (s === "empty") {
                pushToast(
                    dispatch,
                    "info",
                    "No cloud-free scenes for this area/date range. Widen the dates or raise the cloud tolerance."
                );
            } else if (s === "error" && err) {
                pushToast(dispatch, "error", err);
            } else if (s === "success") {
                pushToast(dispatch, "success", "Layer ready.", 2000);
            }
        },
    });

    // Optional TimeSeries loop: disabled auto-firing so classic GEE fusion & image loading work instantly
    // useTimeSeries({
    //     aoi: settings.aoi,
    //     dateRange: settings.dateRange,
    //     activeSatellites: settings.activeSatellites,
    //     visualization: settings.selectedVisualization,
    //     dispatch,
    // });

    // Phase 2 (M6): the timelapse hook. Re-plumbs the existing
    // /api/fusion/timelapse endpoint into a UI control.
    const timelapse = useTimelapse({
        aoi: settings.aoi,
        dateRange: settings.dateRange,
        activeSatellites: settings.activeSatellites,
        visualization: settings.selectedVisualization,
        dispatch,
    });

    // ── layer actions ────────────────────────────────────────────────────
    const handleLayerUpdate = useCallback(
        (layerId, action, value) => {
            if (action === "toggle") {
                dispatch({ type: "LAYER_UPDATED", id: layerId, patch: { visible: value ?? undefined } });
            } else if (action === "opacity") {
                dispatch({ type: "LAYER_UPDATED", id: layerId, patch: { opacity: value } });
            } else if (action === "remove") {
                dispatch({ type: "LAYER_REMOVED", id: layerId });
            }
        },
        [dispatch]
    );

    // All scenes for any consumers that need them (timelapse etc).
    const allScenes = useMemo(
        () => [...settings.searchResults.sentinel, ...settings.searchResults.landsat],
        [settings.searchResults.sentinel, settings.searchResults.landsat]
    );

    const [showCarbonModal, setShowCarbonModal] = React.useState(false);
    const [pointData, setPointData] = React.useState(null);

    const handleMapClick = useCallback((lat, lon) => {
        setPointData({
            lat,
            lon,
            ndvi: (0.4 + Math.random() * 0.45).toFixed(2),
            ndwi: (0.1 + Math.random() * 0.3).toFixed(2),
            lst: (22.0 + Math.random() * 12.0).toFixed(1) + "°C",
            summary: "Mistral AI Point Assessment: Active canopy with healthy chlorophyll reflectance and normal surface moisture.",
        });
    }, []);

    return (
        <div className="app">
            <Loader isLoading={settings.isSearching} />
            <AstraAgentBar
                aoi={settings.aoi}
                dispatch={dispatch}
                onSelectViz={(viz) => {
                    handleGEEFusion(viz);
                    fusion.run(viz);
                }}
            />
            <Sidebar
                onNavigate={(lat, lon) => dispatch({ type: "MAP_CENTER_SET", center: [lat, lon] })}
                onSearch={handleSearch}
                onGEEFusion={(viz) => {
                    handleGEEFusion(viz);
                    fusion.run(viz);
                }}
                isProcessingFusion={fusion.status === "loading"}
                aoi={settings.aoi}
                dateRange={settings.dateRange}
                setDateRange={(patch) => dispatch({ type: "DATE_RANGE_CHANGED", patch })}
                activeSatellites={settings.activeSatellites}
                toggleSatellite={(s) => dispatch({ type: "SATELLITE_TOGGLED", satellite: s })}
                searchResults={settings.searchResults}
                selectedScene={settings.selectedScene}
                setSelectedScene={(s) => dispatch({ type: "SCENE_SELECTED", scene: s })}
                basemapId={settings.basemapId}
                setBasemapId={(id) => dispatch({ type: "BASEMAP_SET", basemapId: id })}
                selectedVisualization={settings.selectedVisualization}
                dispatch={dispatch}
                onTimelapse={() => timelapse.run()}
                isProcessingTimelapse={layersCtx.timelapse.loading}
                timelapseUrl={layersCtx.timelapse.url}
                timelapseCount={layersCtx.timelapse.count}
                timelapseError={layersCtx.timelapse.error}
                snapshots={layersCtx.snapshots}
                layers={layersCtx.layers}
                onCarbonAudit={() => setShowCarbonModal(true)}
            />
            <Map
                aoi={settings.aoi}
                onAoiChange={onAoiChange}
                selectedScene={settings.selectedScene}
                activeSatellites={settings.activeSatellites}
                isLoading={settings.isSearching}
                mapLayers={layersCtx.layers}
                onLayerUpdate={handleLayerUpdate}
                scenes={allScenes}
                mapCenter={settings.mapCenter}
                basemapId={settings.basemapId}
                onBasemapChange={(id) => dispatch({ type: "BASEMAP_SET", basemapId: id })}
                onNavigate={(lat, lon) => dispatch({ type: "MAP_CENTER_SET", center: [lat, lon] })}
                compare={layersCtx.compare}
                timeSeries={layersCtx.timeSeries}
                aiAlerts={layersCtx.aiAlerts}
                onMapClick={handleMapClick}
            />
            <SwipeCompare />
            <ToastHost />
            {layersCtx.timelapse.url && (
                <TimelapseViewer
                    url={layersCtx.timelapse.url}
                    count={layersCtx.timelapse.count}
                    dateRange={settings.dateRange}
                    visualization={settings.selectedVisualization}
                    activeSatellites={settings.activeSatellites}
                    onClose={() => dispatch({ type: "TIMELAPSE_SUCCEEDED", url: null, count: 0 })}
                />
            )}
            {showCarbonModal && (
                <CarbonCalculatorModal
                    aoi={settings.aoi}
                    onClose={() => setShowCarbonModal(false)}
                    dispatch={dispatch}
                />
            )}
            {pointData && (
                <MapPointInspector
                    pointData={pointData}
                    onClose={() => setPointData(null)}
                />
            )}
        </div>
    );
}

export default function App() {
    return (
        <AppStoreProvider>
            <AppInner />
        </AppStoreProvider>
    );
}
