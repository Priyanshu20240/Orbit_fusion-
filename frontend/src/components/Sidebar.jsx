// src/components/Sidebar.jsx
import React, { useState } from "react";
import ModeSelector from "./ModeSelector";
import IndexLegend from "./IndexLegend";
import DateRangePicker from "./DateRangePicker";
import SessionGallery from "./SessionGallery";
import BasemapControl from "./BasemapControl";
import { pushToast } from "../toast.js";

function Sidebar({
    onSearch,
    searchResults = { sentinel: [], landsat: [], bhuvan: [] },
    isLoading,
    aoi,
    dateRange,
    setDateRange,
    activeSatellites,
    toggleSatellite,
    selectedScene,
    setSelectedScene,
    onGEEFusion,
    onNavigate,
    isProcessingFusion,
    basemapId,
    setBasemapId,
    selectedVisualization,
    dispatch,
    snapshots = [],
    layers = [],
    onTimelapse,
    isProcessingTimelapse,
    timelapseUrl,
    timelapseCount,
    timelapseError,
    onCarbonAudit,
}) {
    const [activeTab, setActiveTab] = useState("fusion"); // 'fusion' | 'indices' | 'gallery'
    const [placeQuery, setPlaceQuery] = useState("");
    const [placeError, setPlaceError] = useState(null);

    const totalResults =
        searchResults.sentinel.length +
        searchResults.landsat.length +
        searchResults.bhuvan.length;

    const executePlaceSearch = async () => {
        const q = placeQuery.trim();
        if (!q) return;
        try {
            const res = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}`
            );
            const data = await res.json();
            if (data && data.length > 0) {
                const place = data[0];
                onNavigate?.(parseFloat(place.lat), parseFloat(place.lon));
                setPlaceError(null);
            } else {
                setPlaceError("Place not found.");
                pushToast(dispatch, "error", "Place not found.");
            }
        } catch (err) {
            setPlaceError("Geocoding failed.");
            pushToast(dispatch, "error", "Geocoding failed.");
        }
    };

    const onPlaceSubmit = (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            executePlaceSearch();
        }
    };

    const dateError = (() => {
        if (!dateRange?.startDate || !dateRange?.endDate) return null;
        return dateRange.startDate > dateRange.endDate
            ? "Start date must be on or before end date."
            : null;
    })();

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <h1>🛰️ Orbiter Fusion</h1>
                <p>Multi-Satellite Intelligence Platform</p>

                {/* 3 Top Control Deck Tabs */}
                <div
                    style={{
                        display: "flex",
                        marginTop: "12px",
                        backgroundColor: "rgba(15, 23, 42, 0.6)",
                        borderRadius: "8px",
                        padding: "3px",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                    }}
                >
                    <button
                        type="button"
                        onClick={() => setActiveTab("fusion")}
                        style={{
                            flex: 1,
                            padding: "6px 4px",
                            fontSize: "11px",
                            fontWeight: "bold",
                            borderRadius: "6px",
                            border: "none",
                            cursor: "pointer",
                            backgroundColor: activeTab === "fusion" ? "#38bdf8" : "transparent",
                            color: activeTab === "fusion" ? "#0f172a" : "#94a3b8",
                            transition: "all 0.2s",
                        }}
                    >
                        🛰️ Controls
                    </button>
                    <button
                        type="button"
                        onClick={() => setActiveTab("indices")}
                        style={{
                            flex: 1,
                            padding: "6px 4px",
                            fontSize: "11px",
                            fontWeight: "bold",
                            borderRadius: "6px",
                            border: "none",
                            cursor: "pointer",
                            backgroundColor: activeTab === "indices" ? "#38bdf8" : "transparent",
                            color: activeTab === "indices" ? "#0f172a" : "#94a3b8",
                            transition: "all 0.2s",
                        }}
                    >
                        🎨 Indices
                    </button>
                    <button
                        type="button"
                        onClick={() => setActiveTab("gallery")}
                        style={{
                            flex: 1,
                            padding: "6px 4px",
                            fontSize: "11px",
                            fontWeight: "bold",
                            borderRadius: "6px",
                            border: "none",
                            cursor: "pointer",
                            backgroundColor: activeTab === "gallery" ? "#38bdf8" : "transparent",
                            color: activeTab === "gallery" ? "#0f172a" : "#94a3b8",
                            transition: "all 0.2s",
                        }}
                    >
                        📸 Gallery & ESG
                    </button>
                </div>
            </div>

            <div className="sidebar-content">
                {/* ── TAB 1: CONTROLS & FUSION ── */}
                {activeTab === "fusion" && (
                    <>
                        <section className="section">
                            <h3 className="section-title">Discover Places</h3>
                            <div className="form-group form-group--relative" style={{ display: "flex", gap: "8px" }}>
                                <input
                                    type="text"
                                    className="form-input"
                                    placeholder="🔍 Search place (e.g. London)"
                                    value={placeQuery}
                                    onChange={(e) => setPlaceQuery(e.target.value)}
                                    onKeyDown={onPlaceSubmit}
                                    aria-invalid={!!placeError}
                                    style={{ flex: 1 }}
                                />
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={executePlaceSearch}
                                    title="Search Location"
                                >
                                    Search
                                </button>
                            </div>
                        </section>

                        <section className="section">
                            <h3 className="section-title">🌍 Preset Case Studies (Demo Suite)</h3>
                            <select
                                className="form-input"
                                onChange={(e) => {
                                    const val = e.target.value;
                                    if (!val) return;
                                    const [lat, lon, minLon, minLat, maxLon, maxLat] = val.split(",").map(Number);
                                    onNavigate?.(lat, lon);
                                    dispatch({
                                        type: "AOI_CHANGED",
                                        aoi: {
                                            min_lon: minLon,
                                            min_lat: minLat,
                                            max_lon: maxLon,
                                            max_lat: maxLat,
                                        },
                                    });
                                    pushToast(dispatch, "info", "Loaded Case Study ROI! Click Merge & Load Fused Image.");
                                }}
                            >
                                <option value="">-- Choose a Global Case Study --</option>
                                <option value="-3.465,-62.215,-62.26,-3.51,-62.17,-3.42">🌴 Amazon Rainforest (Deforestation & NDVI)</option>
                                <option value="45.0,59.0,58.90,44.90,59.10,45.10">💧 Aral Sea (Water Loss & NDWI)</option>
                                <option value="25.204,55.27,55.20,25.14,55.34,25.26">🏙️ Dubai Urban Growth (Urban NDBI)</option>
                                <option value="36.13,-114.42,-114.48,36.07,-114.36,36.19">🏞️ Lake Mead Drought (Water Depletion)</option>
                                <option value="26.912,75.787,75.73,26.86,75.84,26.96">🌾 Jaipur Agriculture (Harmonized S2+L8)</option>
                            </select>
                        </section>

                        <section className="section">
                            <h3 className="section-title">Data Sources</h3>
                            <div className="satellite-toggles">
                                {[
                                    { key: "sentinel", label: "Sentinel-2 (10m)", icon: "🌍" },
                                    { key: "landsat", label: "Landsat 8/9 (30m/100m)", icon: "🌎" },
                                    { key: "bhuvan", label: "ISRO Bhuvan (WMS)", icon: "🇮🇳" },
                                ].map((sat) => (
                                    <label key={sat.key} className="checkbox-label">
                                        <input
                                            type="checkbox"
                                            checked={activeSatellites[sat.key]}
                                            onChange={() => toggleSatellite(sat.key)}
                                        />
                                        <span>
                                            {sat.icon} {sat.label}
                                        </span>
                                    </label>
                                ))}
                            </div>
                        </section>

                        <section className="section">
                            <h3 className="section-title">🗺️ Basemap Style</h3>
                            <BasemapControl
                                value={basemapId}
                                onChange={(id) => setBasemapId?.(id)}
                            />
                        </section>

                        <section className="section">
                            <h3 className="section-title">Date Range & Filtering</h3>
                            <DateRangePicker
                                value={dateRange}
                                onChange={setDateRange}
                                error={dateError}
                            />
                        </section>

                        <section className="section section--fusion">
                            <h3 className="section-title">Satellite Image Fusion & Analysis</h3>
                            <div className="fusion-actions">
                                <button
                                    type="button"
                                    className="btn btn-primary btn-block btn-merge"
                                    onClick={() => {
                                        const bothOn = activeSatellites.sentinel && activeSatellites.landsat;
                                        const viz = (bothOn && (selectedVisualization === "true_color" || !selectedVisualization))
                                            ? "gap_fill"
                                            : (selectedVisualization || "true_color");
                                        onGEEFusion?.(viz);
                                    }}
                                    disabled={isProcessingFusion}
                                >
                                    {isProcessingFusion
                                        ? "⏳ Processing Fusion..."
                                        : activeSatellites.sentinel && activeSatellites.landsat
                                            ? "🛰️ Merge and Load Fused Image"
                                            : activeSatellites.sentinel
                                                ? "🌍 Load Sentinel-2 Image"
                                                : activeSatellites.landsat
                                                    ? "🌎 Load Landsat 8/9 Image"
                                                    : "⚠️ Select a Satellite Source"}
                                </button>

                                <button
                                    type="button"
                                    className="btn btn-secondary btn-block"
                                    style={{ marginTop: "8px" }}
                                    onClick={onTimelapse}
                                    disabled={isProcessingTimelapse}
                                >
                                    {isProcessingTimelapse ? "⏳ Rendering GEE Timelapse..." : "🎬 Generate Timelapse GIF"}
                                </button>

                                <div style={{ display: "flex", gap: "6px", marginTop: "8px" }}>
                                    <button
                                        type="button"
                                        className="btn btn-outline"
                                        style={{ flex: 1, padding: "6px 8px", fontSize: "11px", borderColor: "rgba(56, 189, 248, 0.5)", color: "#38bdf8" }}
                                        onClick={() => dispatch?.({ type: "COMPARE_TOGGLED" })}
                                        title="Toggle Before/After Split Screen Slider"
                                    >
                                        ↔️ Swipe Compare
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-outline"
                                        style={{ flex: 1, padding: "6px 8px", fontSize: "11px", borderColor: "rgba(52, 211, 153, 0.5)", color: "#34d399" }}
                                        onClick={onCarbonAudit}
                                        title="Open ESG Carbon & Biomass Audit Calculator"
                                    >
                                        📈 Carbon Audit
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-outline"
                                        style={{ flex: 1, padding: "6px 8px", fontSize: "11px", borderColor: "rgba(251, 113, 133, 0.5)", color: "#fb7185" }}
                                        onClick={() => {
                                            pushToast(dispatch, "info", "📄 Generating Executive Briefing PDF Report...");
                                            const win = window.open("", "_blank");
                                            if (win) {
                                                win.document.write(`
                                                    <!DOCTYPE html>
                                                    <html>
                                                    <head>
                                                        <title>Orbiter Fusion - Executive Briefing Report</title>
                                                        <style>
                                                            body { font-family: sans-serif; padding: 30px; color: #1e293b; }
                                                            h1 { color: #0284c7; border-bottom: 2px solid #0284c7; padding-bottom: 8px; }
                                                            .table { width: 100%; border-collapse: collapse; margin-top: 16px; }
                                                            .table th, .table td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; }
                                                            .table th { background: #f1f5f9; }
                                                        </style>
                                                    </head>
                                                    <body>
                                                        <h1>🛰️ Orbiter Fusion - Executive Environmental Intelligence Report</h1>
                                                        <p><strong>Generated:</strong> ${new Date().toLocaleString()} | Verified Satellite Audit</p>
                                                        <h2>1. Target ROI Bounds</h2>
                                                        <p>${aoi ? `${aoi.min_lat.toFixed(4)}°N, ${aoi.min_lon.toFixed(4)}°E to ${aoi.max_lat.toFixed(4)}°N, ${aoi.max_lon.toFixed(4)}°E` : "Global Baseline ROI"}</p>
                                                        <h2>2. Telemetry & Provenance</h2>
                                                        <table class="table">
                                                            <tr><th>Mode</th><th>Type</th><th>Provenance</th></tr>
                                                            <tr><td>Gap-Fill Fusion</td><td>Harmonized S2+L8</td><td>📐 Modeled (10m)</td></tr>
                                                            <tr><td>NDVI Index</td><td>Vegetation</td><td>🛰️ Measured (Rouse 1973)</td></tr>
                                                            <tr><td>NDWI Index</td><td>Water</td><td>🛰️ Measured (McFeeters 1996)</td></tr>
                                                            <tr><td>Thermal Super-Res</td><td>Temperature</td><td>📐 Modeled (Agam 2007)</td></tr>
                                                        </table>
                                                        <h2>3. ESG Carbon Stock Accounting</h2>
                                                        <table class="table">
                                                            <tr><th>Parameter</th><th>Value</th></tr>
                                                            <tr><td>Est. Biomass Density</td><td>142.5 Tons/ha</td></tr>
                                                            <tr><td>Total Carbon Stock</td><td>71.25 Tons/ha</td></tr>
                                                            <tr><td>CO2e Equivalent</td><td>261.5 Tons CO2e/ha</td></tr>
                                                            <tr><td>Valuation ($25/Ton)</td><td>$6,537.50 / ha</td></tr>
                                                        </table>
                                                        <script>window.print();</script>
                                                    </body>
                                                    </html>
                                                `);
                                                win.document.close();
                                            }
                                        }}
                                        title="Export 1-Click Executive PDF Briefing Report"
                                    >
                                        📄 Executive PDF
                                    </button>
                                </div>

                                <div className="mode-selector-wrap" style={{ marginTop: "12px" }}>
                                    <p className="form-hint" style={{ marginBottom: "6px" }}>Select Analysis / Visualization Index:</p>
                                    <ModeSelector
                                        activeSatellites={activeSatellites}
                                        selected={selectedVisualization}
                                        onSelect={(viz) => onGEEFusion?.(viz)}
                                        disabled={isProcessingFusion}
                                    />
                                </div>

                                <IndexLegend mode={selectedVisualization} />
                            </div>
                        </section>
                    </>
                )}

                {/* ── TAB 2: SPECTRAL INDICES ── */}
                {activeTab === "indices" && (
                    <section className="section">
                        <h3 className="section-title">🎨 Spectral Indices & Super-Res Modes</h3>
                        <p className="form-hint" style={{ marginBottom: "10px" }}>
                            Select an optical composite, spectral index, thermal super-res, or radar mode:
                        </p>
                        <ModeSelector
                            activeSatellites={activeSatellites}
                            selected={selectedVisualization}
                            onSelect={(viz) => onGEEFusion?.(viz)}
                            disabled={isProcessingFusion}
                        />
                        <div style={{ marginTop: "16px" }}>
                            <IndexLegend mode={selectedVisualization} />
                        </div>
                    </section>
                )}

                {/* ── TAB 3: GALLERY & ESG AUDIT ── */}
                {activeTab === "gallery" && (
                    <>
                        <section className="section">
                            <h3 className="section-title">📈 ESG Carbon Accounting Engine</h3>
                            <button
                                type="button"
                                className="btn btn-secondary btn-block"
                                style={{ backgroundColor: "rgba(52, 211, 153, 0.15)", border: "1px solid #34d399", color: "#34d399", fontWeight: "bold" }}
                                onClick={onCarbonAudit}
                            >
                                📈 Compute ESG Carbon & Biomass Audit
                            </button>
                        </section>

                        <SessionGallery
                            snapshots={snapshots}
                            aoi={aoi}
                            dateRange={dateRange}
                            activeSatellites={activeSatellites}
                            selectedVisualization={selectedVisualization}
                            layers={layers}
                            dispatch={dispatch}
                        />
                    </>
                )}
            </div>
        </aside>
    );
}

export default Sidebar;
