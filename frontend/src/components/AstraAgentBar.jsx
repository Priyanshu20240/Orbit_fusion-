// src/components/AstraAgentBar.jsx
import React, { useState } from "react";
import { request } from "../api/client.js";
import { pushToast } from "../toast.js";

export default function AstraAgentBar({ aoi, dispatch, onSelectViz }) {
    const [prompt, setPrompt] = useState("");
    const [loading, setLoading] = useState(false);
    const [agentResult, setAgentResult] = useState(null);

    const runAgentQuery = async (queryText) => {
        const text = queryText || prompt;
        if (!text.trim()) return;

        setLoading(true);
        try {
            const bounds = aoi
                ? [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat]
                : [77.55, 12.95, 77.62, 13.02];

            const res = await request("/api/ai/astra-query", {
                body: { prompt: text, bounds },
            });

            setAgentResult(res);
            pushToast(dispatch, "success", `ASTRA-AI: ${res.anomaly_type} complete! 🤖`);

            // Dispatch alert pins & polygons to store for rendering on Map
            if (res.alert_pins || res.alert_polygons) {
                dispatch({
                    type: "AI_ALERTS_SET",
                    pins: res.alert_pins || [],
                    polygons: res.alert_polygons || [],
                });
            }

            // Automatically switch visualization to the recommended index
            if (res.recommended_viz && onSelectViz) {
                onSelectViz(res.recommended_viz);
            }
        } catch (err) {
            pushToast(dispatch, "error", "ASTRA-AI Query failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            style={{
                position: "fixed",
                top: "10px",
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 9998,
                width: "85%",
                maxWidth: "580px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
            }}
        >
            {/* Command Bar Input */}
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    backgroundColor: "rgba(15, 23, 42, 0.92)",
                    backdropFilter: "blur(12px)",
                    border: "1.5px solid rgba(56, 189, 248, 0.5)",
                    borderRadius: "20px",
                    padding: "4px 10px",
                    boxShadow: "0 8px 20px rgba(0, 0, 0, 0.5)",
                }}
            >
                <span style={{ fontSize: "13px" }}>🤖</span>
                <input
                    type="text"
                    className="form-input"
                    placeholder="ASTRA-AI Prompt (e.g. Scan for deforestation or reservoir loss)..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && runAgentQuery()}
                    style={{
                        flex: 1,
                        background: "none",
                        border: "none",
                        color: "#fff",
                        fontSize: "11px",
                        outline: "none",
                        boxShadow: "none",
                    }}
                />
                <button
                    type="button"
                    className="btn btn--primary"
                    onClick={() => runAgentQuery()}
                    disabled={loading}
                    style={{ padding: "4px 12px", fontSize: "11px", borderRadius: "14px" }}
                >
                    {loading ? "⚡ Scanning..." : "Run AI Scan"}
                </button>
            </div>

            {/* Quick Sample Prompts */}
            <div style={{ display: "flex", gap: "6px", overflowX: "auto", paddingBottom: "2px" }}>
                <button
                    type="button"
                    className="badge badge--info"
                    style={{ cursor: "pointer", fontSize: "11px", whiteSpace: "nowrap", backgroundColor: "rgba(239, 68, 68, 0.2)", border: "1px solid #ef4444" }}
                    onClick={() => {
                        const p = "Scan this province for illegal deforestation or forest fires over the last 6 months";
                        setPrompt(p);
                        runAgentQuery(p);
                    }}
                >
                    🌴 Deforestation & Wildfire Scan
                </button>
                <button
                    type="button"
                    className="badge badge--info"
                    style={{ cursor: "pointer", fontSize: "11px", whiteSpace: "nowrap", backgroundColor: "rgba(2, 132, 199, 0.2)", border: "1px solid #0284c7" }}
                    onClick={() => {
                        const p = "Identify solar farms or water reservoirs that shrank by more than 15% this summer";
                        setPrompt(p);
                        runAgentQuery(p);
                    }}
                >
                    💧 Water Reservoir Shrinkage Scan
                </button>
                <button
                    type="button"
                    className="badge badge--info"
                    style={{ cursor: "pointer", fontSize: "11px", whiteSpace: "nowrap", backgroundColor: "rgba(249, 115, 22, 0.2)", border: "1px solid #f97316" }}
                    onClick={() => {
                        const p = "Detect urban heat islands and building energy leaks";
                        setPrompt(p);
                        runAgentQuery(p);
                    }}
                >
                    🌡️ 10m Urban Heat Island Scan
                </button>
            </div>

            {/* AI Result Card */}
            {agentResult && (
                <div
                    style={{
                        backgroundColor: "rgba(30, 41, 59, 0.95)",
                        backdropFilter: "blur(12px)",
                        border: "1px solid rgba(56, 189, 248, 0.6)",
                        borderRadius: "12px",
                        padding: "14px 18px",
                        color: "#fff",
                        fontSize: "12px",
                        boxShadow: "0 12px 28px rgba(0, 0, 0, 0.6)",
                    }}
                >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontWeight: "bold" }}>
                        <span style={{ color: "#38bdf8", fontSize: "14px" }}>🚨 {agentResult.anomaly_type}</span>
                        <button
                            type="button"
                            onClick={() => {
                                setAgentResult(null);
                                dispatch({ type: "AI_ALERTS_SET", pins: [], polygons: [] });
                            }}
                            style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "14px" }}
                        >
                            ✖️
                        </button>
                    </div>

                    <p style={{ margin: "8px 0 4px 0", color: "#e2e8f0", lineHeight: "1.4" }}>{agentResult.summary}</p>
                    <div style={{ marginTop: "6px", color: "#34d399", fontSize: "12px" }}>
                        💡 <strong>Recommended Action:</strong> {agentResult.action_recommended}
                    </div>
                </div>
            )}
        </div>
    );
}
