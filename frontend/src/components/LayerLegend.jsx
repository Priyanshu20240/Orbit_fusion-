// src/components/LayerLegend.jsx
import React from "react";

const LEGEND_CONFIGS = {
  ndvi: {
    title: "NDVI (Vegetation Index)",
    minLabel: "-0.2 (Sparse/Water)",
    maxLabel: "+0.8 (Dense Canopy)",
    gradient: "linear-gradient(to right, #000080, #4575b4, #e0f3f8, #fee090, #d9ef8b, #91cf60, #1a9850, #004d00)"
  },
  ndwi: {
    title: "NDWI (Water Index)",
    minLabel: "-0.3 (Land/Dry)",
    maxLabel: "+0.5 (Water Body)",
    gradient: "linear-gradient(to right, #fdae61, #ffffbf, #e0f3f8, #abd9e9, #2c7fb8, #253494, #081d58)"
  },
  ndbi: {
    title: "NDBI (Built-up Index)",
    minLabel: "-0.4 (Vegetation)",
    maxLabel: "+0.4 (Urban Concrete)",
    gradient: "linear-gradient(to right, #1a9850, #91cf60, #ffffbf, #fdae61, #d73027)"
  },
  lst: {
    title: "RealLST Land Temp (°C)",
    minLabel: "15°C (Cool)",
    maxLabel: "45°C (Extreme Heat)",
    gradient: "linear-gradient(to right, #313695, #4575b4, #74add1, #abd9e9, #e0f3f8, #fee090, #fdae61, #f46d43, #d73027)"
  },
  real_lst: {
    title: "Emissivity-Adjusted LST (°C)",
    minLabel: "15°C (Cool)",
    maxLabel: "45°C (Hot)",
    gradient: "linear-gradient(to right, #313695, #4575b4, #74add1, #abd9e9, #e0f3f8, #fee090, #fdae61, #f46d43, #d73027)"
  }
};

export default function LayerLegend({ strategy = "ndvi" }) {
  const config = LEGEND_CONFIGS[strategy];
  if (!config) return null;

  return (
    <div style={{
      position: "absolute",
      bottom: "28px",
      left: "12px",
      zIndex: 1000,
      background: "rgba(15, 23, 42, 0.85)",
      backdropFilter: "blur(8px)",
      border: "1px solid rgba(255, 255, 255, 0.15)",
      borderRadius: "8px",
      padding: "8px 12px",
      color: "#f8fafc",
      fontSize: "11px",
      boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
      minWidth: "220px"
    }}>
      <div style={{ fontWeight: "bold", marginBottom: "4px", color: "#38bdf8" }}>
        {config.title}
      </div>
      <div style={{
        height: "10px",
        borderRadius: "4px",
        background: config.gradient,
        marginBottom: "4px",
        border: "1px solid rgba(255, 255, 255, 0.2)"
      }} />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#94a3b8" }}>
        <span>{config.minLabel}</span>
        <span>{config.maxLabel}</span>
      </div>
    </div>
  );
}
