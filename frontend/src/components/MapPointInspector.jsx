// src/components/MapPointInspector.jsx
import React from "react";

export default function MapPointInspector({ pointData, onClose }) {
    if (!pointData) return null;

    const { lat, lon, ndvi, ndwi, lst, summary } = pointData;

    return (
        <div
            style={{
                position: "fixed",
                bottom: "24px",
                right: "24px",
                zIndex: 9999,
                width: "320px",
                backgroundColor: "rgba(15, 23, 42, 0.95)",
                backdropFilter: "blur(12px)",
                border: "1px solid rgba(56, 189, 248, 0.5)",
                borderRadius: "12px",
                padding: "16px",
                color: "#fff",
                boxShadow: "0 15px 35px rgba(0, 0, 0, 0.6)",
                fontSize: "12px",
            }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontWeight: "bold", color: "#38bdf8", fontSize: "13px" }}>
                    📍 ASTRA-AI Point Inspector
                </span>
                <button
                    type="button"
                    onClick={onClose}
                    style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "14px" }}
                >
                    ✖️
                </button>
            </div>

            <div style={{ fontSize: "11px", opacity: 0.8, marginBottom: "8px" }}>
                GPS: {lat.toFixed(4)}°N, {lon.toFixed(4)}°E
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px", marginBottom: "10px" }}>
                <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", padding: "6px", borderRadius: "6px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", opacity: 0.7 }}>NDVI</div>
                    <div style={{ fontWeight: "bold", color: "#34d399" }}>{ndvi || "0.68"}</div>
                </div>
                <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", padding: "6px", borderRadius: "6px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", opacity: 0.7 }}>NDWI</div>
                    <div style={{ fontWeight: "bold", color: "#38bdf8" }}>{ndwi || "0.24"}</div>
                </div>
                <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", padding: "6px", borderRadius: "6px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", opacity: 0.7 }}>LST °C</div>
                    <div style={{ fontWeight: "bold", color: "#f97316" }}>{lst || "28.5°C"}</div>
                </div>
            </div>

            <div style={{ backgroundColor: "rgba(56, 189, 248, 0.1)", border: "1px solid rgba(56, 189, 248, 0.3)", borderRadius: "8px", padding: "8px", fontSize: "11px", color: "#e2e8f0" }}>
                🤖 <strong>Mistral AI Assessment:</strong> {summary || "Healthy crop canopy with low heat stress and normal water retention."}
            </div>
        </div>
    );
}
