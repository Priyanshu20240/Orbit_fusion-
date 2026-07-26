// src/components/LayerControl.jsx
//
// M9 — config-driven. Layer items now read their badge/label/icon from
// the GEE-fusion layer shape (kind, mode, satellite) and from
// config/visualizations.js for the mode-specific accent. No more
// hardcoded RGB/NDVI/WMS branches. Styles hoisted to index.css.

import { useState } from "react";
import { VISUALIZATIONS_BY_ID } from "../config/visualizations.js";

function layerBadge(layer) {
    if (layer.kind === "gee") {
        const v = VISUALIZATIONS_BY_ID[layer.mode];
        return v ? `${v.icon} ${v.label}` : `GEE · ${layer.mode}`;
    }
    if (layer.kind === "wms" || layer.satellite === "bhuvan") {
        return "🇮🇳 WMS";
    }
    return layer.satellite || "layer";
}

function layerName(layer) {
    if (layer.kind === "gee") {
        const v = VISUALIZATIONS_BY_ID[layer.mode];
        return v ? `GEE Fusion (${v.label})` : layer.name;
    }
    return layer.name || layer.id;
}

export default function LayerControl({ layers, onToggleLayer, onOpacityChange, onRemoveLayer }) {
    const [expanded, setExpanded] = useState(true);
    if (!layers || layers.length === 0) return null;

    return (
        <div className="layer-control">
            <button
                type="button"
                className="layer-control-header"
                onClick={() => setExpanded((v) => !v)}
                aria-expanded={expanded}
                aria-controls="layer-control-content"
            >
                <span>🗂️ Active Layers ({layers.length})</span>
                <span className="layer-control-icon" aria-hidden="true">
                    {expanded ? "▼" : "▶"}
                </span>
            </button>

            {expanded && (
                <div className="layer-control-content" id="layer-control-content">
                    {layers.map((layer) => (
                        <div key={layer.id} className="layer-item">
                            <div className="layer-item-header">
                                <label className="layer-checkbox">
                                    <input
                                        type="checkbox"
                                        checked={!!layer.visible}
                                        onChange={() => onToggleLayer(layer.id)}
                                        aria-label={`Toggle ${layerName(layer)}`}
                                    />
                                    <span className="layer-name">{layerName(layer)}</span>
                                </label>
                                <button
                                    type="button"
                                    className="layer-remove-btn"
                                    onClick={() => onRemoveLayer(layer.id)}
                                    title="Remove layer"
                                    aria-label={`Remove ${layerName(layer)}`}
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="layer-opacity">
                                <span className="opacity-label">Opacity</span>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={layer.opacity ?? 100}
                                    onChange={(e) => onOpacityChange(layer.id, parseInt(e.target.value, 10))}
                                    className="opacity-slider"
                                    aria-label={`Opacity for ${layerName(layer)}`}
                                />
                                <span className="opacity-value">{layer.opacity ?? 100}%</span>
                            </div>

                            <div className="layer-type">
                                <span className={`layer-badge layer-badge--${layer.kind || "layer"}`}>
                                    {layerBadge(layer)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
