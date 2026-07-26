// src/components/TimelapseViewer.jsx
import React from "react";

export default function TimelapseViewer({
    url,
    count,
    dateRange,
    visualization,
    activeSatellites,
    onClose,
}) {
    if (!url) return null;

    const sensorList = Object.entries(activeSatellites || {})
        .filter(([, v]) => v)
        .map(([k]) => k.toUpperCase())
        .join(" + ");

    const downloadGif = () => {
        const a = document.createElement("a");
        a.href = url;
        a.download = `orbiter-timelapse-${visualization || "fused"}-${Date.now()}.gif`;
        a.target = "_blank";
        a.click();
    };

    return (
        <div
            style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                zIndex: 10000,
                backgroundColor: "rgba(15, 23, 42, 0.85)",
                backdropFilter: "blur(12px)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "24px",
            }}
        >
            <div
                style={{
                    backgroundColor: "#1e293b",
                    borderRadius: "16px",
                    border: "1px solid rgba(255, 255, 255, 0.15)",
                    boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
                    maxWidth: "720px",
                    width: "100%",
                    display: "flex",
                    flexDirection: "column",
                    overflow: "hidden",
                }}
            >
                {/* Header Badge */}
                <div
                    style={{
                        padding: "16px 20px",
                        backgroundColor: "#0f172a",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                    }}
                >
                    <div>
                        <h3 style={{ margin: 0, color: "#38bdf8", fontSize: "16px", fontWeight: 700 }}>
                            🎬 Google Earth Engine Fused Timelapse
                        </h3>
                        <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                            📅 {dateRange?.startDate} → {dateRange?.endDate} | 🛰️ {sensorList || "SATELLITE"} | 🎞️ {count} Frames
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                        style={{
                            background: "none",
                            border: "none",
                            color: "#94a3b8",
                            fontSize: "20px",
                            cursor: "pointer",
                            padding: "4px 8px",
                            borderRadius: "6px",
                        }}
                        title="Close Viewer"
                    >
                        ✖️
                    </button>
                </div>

                {/* Animated GIF Container with Floating Overlay */}
                <div
                    style={{
                        position: "relative",
                        width: "100%",
                        maxHeight: "480px",
                        backgroundColor: "#090d16",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        overflow: "hidden",
                    }}
                >
                    {/* Live Floating Date HUD Badge over GIF */}
                    <div
                        style={{
                            position: "absolute",
                            top: "12px",
                            left: "12px",
                            zIndex: 10,
                            backgroundColor: "rgba(15, 23, 42, 0.85)",
                            backdropFilter: "blur(6px)",
                            border: "1px solid rgba(56, 189, 248, 0.4)",
                            borderRadius: "12px",
                            padding: "4px 12px",
                            color: "#38bdf8",
                            fontSize: "12px",
                            fontWeight: 600,
                        }}
                    >
                        📅 {dateRange?.startDate} → {dateRange?.endDate} ({visualization?.toUpperCase()})
                    </div>

                    <img
                        src={url}
                        alt="GEE Satellite Timelapse"
                        style={{
                            maxWidth: "100%",
                            maxHeight: "460px",
                            objectFit: "contain",
                            display: "block",
                        }}
                    />
                </div>

                {/* Footer Controls */}
                <div
                    style={{
                        padding: "14px 20px",
                        backgroundColor: "#0f172a",
                        borderTop: "1px solid rgba(255, 255, 255, 0.1)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                    }}
                >
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                        Format: High-Volume GEE Video Stream (.gif)
                    </div>

                    <div style={{ display: "flex", gap: "10px" }}>
                        <button
                            type="button"
                            className="btn btn--primary"
                            onClick={downloadGif}
                            style={{ padding: "8px 16px", fontSize: "13px" }}
                        >
                            ⬇️ Save Timelapse GIF to Disk
                        </button>
                        <button
                            type="button"
                            className="btn btn--secondary"
                            onClick={onClose}
                            style={{ padding: "8px 16px", fontSize: "13px" }}
                        >
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
