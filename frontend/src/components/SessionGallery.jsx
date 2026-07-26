// src/components/SessionGallery.jsx
import React from "react";
import { SNAPSHOT_SAVED, SNAPSHOT_REMOVED } from "../state/actions.js";
import { pushToast } from "../toast.js";

export default function SessionGallery({
    snapshots = [],
    aoi,
    dateRange,
    activeSatellites,
    selectedVisualization,
    layers = [],
    dispatch,
}) {
    const activeFusionLayer = layers.find((l) => l.idPrefix === "gee-fusion-");

    const saveCurrentSnapshot = () => {
        if (!aoi) {
            pushToast(dispatch, "error", "Draw an ROI on the map first to save a snapshot.");
            return;
        }

        const snapshot = {
            id: `snap-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            dateRange: { ...dateRange },
            activeSatellites: { ...activeSatellites },
            visualization: selectedVisualization,
            fusionId: activeFusionLayer?.fusionId || "gee-fused-layer",
            tileUrl: activeFusionLayer?.tileUrl || null,
            aoiBounds: aoi ? [
                aoi.min_lon?.toFixed(4),
                aoi.min_lat?.toFixed(4),
                aoi.max_lon?.toFixed(4),
                aoi.max_lat?.toFixed(4),
            ].join(", ") : "Global",
        };

        dispatch({ type: SNAPSHOT_SAVED, snapshot });
        pushToast(dispatch, "success", "Saved current ROI image to Session Gallery! 📷");
    };

    const deleteSnapshot = (id) => {
        dispatch({ type: SNAPSHOT_REMOVED, id });
        pushToast(dispatch, "info", "Snapshot removed.");
    };

    const downloadImagePNG = (snap) => {
        const canvas = document.createElement("canvas");
        canvas.width = 800;
        canvas.height = 600;
        const ctx = canvas.getContext("2d");

        // Background
        ctx.fillStyle = "#121826";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw Map Tiles from DOM if present
        const tileImgs = document.querySelectorAll(".leaflet-tile");
        let tilesDrawn = 0;

        const drawOverlayAndDownload = () => {
            // Draw Metadata Header Overlay Badge
            ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
            ctx.fillRect(20, 20, 420, 140);
            ctx.strokeStyle = "rgba(59, 130, 246, 0.5)";
            ctx.lineWidth = 1;
            ctx.strokeRect(20, 20, 420, 140);

            ctx.fillStyle = "#60a5fa";
            ctx.font = "bold 16px sans-serif";
            ctx.fillText(`🛰️ ORBITER FUSION — ${snap.visualization.toUpperCase()}`, 35, 48);

            ctx.fillStyle = "#e2e8f0";
            ctx.font = "12px sans-serif";
            ctx.fillText(`📅 Dates: ${snap.dateRange.startDate} to ${snap.dateRange.endDate}`, 35, 75);
            ctx.fillText(`📡 Sensors: ${Object.entries(snap.activeSatellites).filter(([, v]) => v).map(([k]) => k.toUpperCase()).join(" + ")}`, 35, 95);
            ctx.fillText(`📍 Bounds: [${snap.aoiBounds}]`, 35, 115);
            ctx.fillText(`🆔 GEE Map ID: ${snap.fusionId}`, 35, 135);

            // Export to Disk
            const dataUrl = canvas.toDataURL("image/png");
            const a = document.createElement("a");
            a.href = dataUrl;
            a.download = `orbiter-fusion-${snap.visualization}-${snap.id}.png`;
            a.click();
            pushToast(dispatch, "success", "Saved satellite PNG to disk! 🖼️");
        };

        if (tileImgs.length > 0) {
            tileImgs.forEach((img) => {
                try {
                    const rect = img.getBoundingClientRect();
                    const mapEl = document.querySelector(".leaflet-container");
                    if (mapEl) {
                        const mapRect = mapEl.getBoundingClientRect();
                        const x = ((rect.left - mapRect.left) / mapRect.width) * canvas.width;
                        const y = ((rect.top - mapRect.top) / mapRect.height) * canvas.height;
                        const w = (rect.width / mapRect.width) * canvas.width;
                        const h = (rect.height / mapRect.height) * canvas.height;
                        ctx.drawImage(img, x, y, w, h);
                        tilesDrawn++;
                    }
                } catch (e) {
                    // CORS or unrendered tile safety fallback
                }
            });
        }

        drawOverlayAndDownload();
    };

    const downloadMetadataText = (snap) => {
        const text = `================================================
ORBITER FUSION — SATELLITE SNAPSHOT METADATA
================================================
Snapshot ID:      ${snap.id}
Saved Time:       ${snap.timestamp}
Visualization:    ${snap.visualization.toUpperCase()}
Date Window:      ${snap.dateRange.startDate} to ${snap.dateRange.endDate}
Active Sensors:   ${Object.entries(snap.activeSatellites).filter(([, v]) => v).map(([k]) => k).join(", ")}
ROI Bounds:       [${snap.aoiBounds}]
GEE Fusion ID:    ${snap.fusionId}
================================================`;

        const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `orbiter-fusion-${snap.visualization}-${snap.id}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const exportGeoJSON = () => {
        if (!aoi) {
            pushToast(dispatch, "error", "No active ROI geometry to export.");
            return;
        }

        const geojson = aoi.geojson || {
            type: "Feature",
            geometry: {
                type: "Polygon",
                coordinates: [[
                    [aoi.min_lon, aoi.min_lat],
                    [aoi.max_lon, aoi.min_lat],
                    [aoi.max_lon, aoi.max_lat],
                    [aoi.min_lon, aoi.max_lat],
                    [aoi.min_lon, aoi.min_lat],
                ]],
            },
            properties: { name: "Orbiter Fusion ROI" },
        };

        const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `orbiter-fusion-roi-${Date.now()}.geojson`;
        a.click();
        URL.revokeObjectURL(url);
        pushToast(dispatch, "success", "Exported GeoJSON ROI! 🌐");
    };

    const exportCSVReport = () => {
        if (snapshots.length === 0) {
            pushToast(dispatch, "error", "No session snapshots to export.");
            return;
        }

        const headers = ["Snapshot ID", "Time", "Visualization", "Start Date", "End Date", "Sensors", "ROI Bounds", "GEE Fusion ID"];
        const rows = snapshots.map((s) => [
            s.id,
            s.timestamp,
            s.visualization,
            s.dateRange.startDate,
            s.dateRange.endDate,
            Object.entries(s.activeSatellites).filter(([, v]) => v).map(([k]) => k).join("+"),
            `"${s.aoiBounds}"`,
            s.fusionId,
        ]);

        const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `orbiter-fusion-session-report-${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        pushToast(dispatch, "success", "Exported Session CSV Log! 📄");
    };

    return (
        <section className="section" style={{ marginTop: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 className="section-title" style={{ margin: 0 }}>📷 Session Snapshot Gallery</h3>
                <span className="badge badge--info" style={{ fontSize: "11px" }}>{snapshots.length} saved</span>
            </div>

            <div style={{ display: "flex", gap: "8px", marginTop: "10px", flexWrap: "wrap" }}>
                <button
                    className="btn btn--primary"
                    style={{ flex: 1, padding: "6px 10px", fontSize: "12px" }}
                    onClick={saveCurrentSnapshot}
                >
                    📸 Save Current ROI Image
                </button>
                <button
                    className="btn btn--secondary"
                    style={{ padding: "6px 10px", fontSize: "12px" }}
                    onClick={exportGeoJSON}
                >
                    🌐 Export GeoJSON
                </button>
            </div>

            {snapshots.length > 0 && (
                <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "10px" }}>
                    <button
                        className="btn btn--secondary"
                        style={{ width: "100%", padding: "6px", fontSize: "12px" }}
                        onClick={exportCSVReport}
                    >
                        📄 Export Session CSV Log
                    </button>

                    <div style={{ maxHeight: "220px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
                        {snapshots.map((snap) => (
                            <div
                                key={snap.id}
                                className="card"
                                style={{
                                    padding: "8px 12px",
                                    fontSize: "12px",
                                    borderRadius: "6px",
                                    backgroundColor: "rgba(255,255,255,0.04)",
                                    border: "1px solid rgba(255,255,255,0.1)",
                                }}
                            >
                                <div style={{ display: "flex", justifyContent: "space-between", fontWeight: "bold" }}>
                                    <span>🖼️ {snap.visualization.toUpperCase()}</span>
                                    <span style={{ opacity: 0.7, fontSize: "11px" }}>{snap.timestamp}</span>
                                </div>
                                <div style={{ fontSize: "11px", opacity: "0.8", marginTop: "4px" }}>
                                    📅 {snap.dateRange.startDate} → {snap.dateRange.endDate}
                                </div>
                                <div style={{ fontSize: "11px", opacity: "0.8" }}>
                                    📍 Bounds: [{snap.aoiBounds}]
                                </div>

                                <div style={{ display: "flex", gap: "6px", marginTop: "8px", flexWrap: "wrap" }}>
                                    <button
                                        className="btn btn--primary"
                                        style={{ padding: "3px 8px", fontSize: "11px", flex: 1 }}
                                        onClick={() => downloadImagePNG(snap)}
                                    >
                                        🖼️ Save PNG Image
                                    </button>
                                    <button
                                        className="btn btn--secondary"
                                        style={{ padding: "3px 8px", fontSize: "11px" }}
                                        onClick={() => downloadMetadataText(snap)}
                                    >
                                        📥 Metadata TXT
                                    </button>
                                    <button
                                        className="btn btn--danger"
                                        style={{ padding: "3px 8px", fontSize: "11px" }}
                                        onClick={() => deleteSnapshot(snap.id)}
                                    >
                                        🗑️ Delete
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </section>
    );
}
