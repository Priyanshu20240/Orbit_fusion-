// src/components/CarbonCalculatorModal.jsx
import React, { useState, useEffect } from "react";
import { request } from "../api/client.js";
import { pushToast } from "../toast.js";

export default function CarbonCalculatorModal({ aoi, onClose, dispatch }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchCarbonData = async () => {
            setLoading(true);
            try {
                const bounds = aoi
                    ? [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat]
                    : [77.55, 12.95, 77.62, 13.02];

                const res = await request("/api/analytics/carbon-audit", {
                    body: { bounds, mean_ndvi: 0.68, mean_evi: 0.52, carbon_price: 25.0 },
                });
                setData(res);
            } catch (err) {
                pushToast(dispatch, "error", "Failed to compute Carbon Audit.");
            } finally {
                setLoading(false);
            }
        };

        fetchCarbonData();
    }, [aoi, dispatch]);

    const downloadPDFReport = () => {
        if (!data) return;
        const reportText = `================================================
ORBITER FUSION (ASTRAVISION) — ESG CARBON AUDIT REPORT
================================================
Audit Timestamp:         ${new Date().toLocaleString()}
Verification Protocol:   ${data.verification_protocol}
ESG Rating:              ${data.esg_rating}
Canopy Health:           ${data.forest_health_status}

SPATIAL & BIOMASS METRICS:
------------------------------------------------
ROI Area (Hectares):     ${data.area_hectares} ha
Mean NDVI / EVI:         ${data.mean_ndvi} / ${data.mean_evi}
Biomass Density:         ${data.biomass_density_tons_per_ha} Tons Dry Biomass / ha
Total Canopy Biomass:    ${data.total_biomass_tons} Tons
Total Carbon Stock:      ${data.total_carbon_stock_tons} Tons Carbon

CARBON CREDIT ESTIMATE:
------------------------------------------------
Equivalent CO2 (CO2e):   ${data.total_co2e_tons} Tons CO2e
Carbon Price Benchmark:  $${data.carbon_price_per_ton_usd} / Ton CO2e
Estimated Credit Value:  $${data.estimated_credit_value_usd.toLocaleString()} USD
================================================`;

        const blob = new Blob([reportText], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `esg-carbon-audit-${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        pushToast(dispatch, "success", "Exported ESG Carbon Audit Report! 📄");
    };

    return (
        <div
            style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                zIndex: 10001,
                backgroundColor: "rgba(15, 23, 42, 0.85)",
                backdropFilter: "blur(12px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "20px",
            }}
        >
            <div
                style={{
                    backgroundColor: "#1e293b",
                    borderRadius: "16px",
                    border: "1px solid rgba(52, 211, 153, 0.4)",
                    boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
                    maxWidth: "600px",
                    width: "100%",
                    padding: "24px",
                    color: "#fff",
                }}
            >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0, color: "#34d399", fontSize: "18px" }}>
                        📈 ESG Carbon Credit & Biomass Verification Engine
                    </h3>
                    <button
                        type="button"
                        onClick={onClose}
                        style={{ background: "none", border: "none", color: "#94a3b8", fontSize: "18px", cursor: "pointer" }}
                    >
                        ✖️
                    </button>
                </div>

                {loading ? (
                    <div style={{ padding: "30px 0", textAlign: "center", color: "#94a3b8" }}>
                        ⏳ Computing IPCC Tier-2 Biomass & Carbon Stock...
                    </div>
                ) : data ? (
                    <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px", fontSize: "13px" }}>
                        <div style={{ padding: "10px 14px", borderRadius: "8px", backgroundColor: "rgba(52, 211, 153, 0.1)", border: "1px solid rgba(52, 211, 153, 0.3)" }}>
                            <div style={{ fontWeight: "bold", color: "#34d399" }}>{data.esg_rating}</div>
                            <div style={{ fontSize: "12px", opacity: 0.8 }}>{data.forest_health_status}</div>
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                            <div className="card" style={{ padding: "10px" }}>
                                <div style={{ fontSize: "11px", opacity: 0.7 }}>ROI Forest Area</div>
                                <div style={{ fontSize: "16px", fontWeight: "bold", color: "#38bdf8" }}>{data.area_hectares} ha</div>
                            </div>
                            <div className="card" style={{ padding: "10px" }}>
                                <div style={{ fontSize: "11px", opacity: 0.7 }}>Biomass Density</div>
                                <div style={{ fontSize: "16px", fontWeight: "bold", color: "#34d399" }}>{data.biomass_density_tons_per_ha} T / ha</div>
                            </div>
                            <div className="card" style={{ padding: "10px" }}>
                                <div style={{ fontSize: "11px", opacity: 0.7 }}>Total Carbon Stock</div>
                                <div style={{ fontSize: "16px", fontWeight: "bold", color: "#fbbf24" }}>{data.total_carbon_stock_tons} Tons C</div>
                            </div>
                            <div className="card" style={{ padding: "10px" }}>
                                <div style={{ fontSize: "11px", opacity: 0.7 }}>CO2 Sequestration Value</div>
                                <div style={{ fontSize: "16px", fontWeight: "bold", color: "#34d399" }}>${data.estimated_credit_value_usd.toLocaleString()} USD</div>
                            </div>
                        </div>

                        <div style={{ fontSize: "11px", opacity: 0.6, marginTop: "4px" }}>
                            Protocol: {data.verification_protocol} | Benchmark: ${data.carbon_price_per_ton_usd}/Ton CO2e
                        </div>

                        <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
                            <button
                                type="button"
                                className="btn btn--primary"
                                onClick={downloadPDFReport}
                                style={{ flex: 1, padding: "8px" }}
                            >
                                📄 Export ESG Carbon Audit Report
                            </button>
                            <button
                                type="button"
                                className="btn btn--secondary"
                                onClick={onClose}
                                style={{ padding: "8px 16px" }}
                            >
                                Close
                            </button>
                        </div>
                    </div>
                ) : null}
            </div>
        </div>
    );
}
