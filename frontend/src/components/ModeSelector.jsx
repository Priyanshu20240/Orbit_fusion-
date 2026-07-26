// src/components/ModeSelector.jsx
//
// M9 — config-driven visualization picker. Renders the 8 P0 modes
// (True Color, NDVI, NDWI, NDBI, NIR Composite, SWIR Composite, SCI,
// LST) using the existing VizButton primitive. LST is disabled when
// only Sentinel is selected. The currently-active mode is marked
// `aria-pressed`. a11y: outer role="radiogroup".

import VizButton from "./Sidebar/VizButton.jsx";
import { availableFor, VISUALIZATIONS } from "../config/visualizations.js";

function activePlatforms(activeSatellites) {
    return Object.keys(activeSatellites || {}).filter(
        (k) => activeSatellites[k]
    );
}

export default function ModeSelector({ activeSatellites, selected, onSelect, disabled }) {
    const allowed = new Set(availableFor(activePlatforms(activeSatellites)).map((v) => v.id));
    return (
        <div className="mode-selector" role="radiogroup" aria-label="Visualization mode">
            {VISUALIZATIONS.map((viz) => {
                const isDisabled = disabled || !allowed.has(viz.id);
                return (
                    <VizButton
                        key={viz.id}
                        viz={viz}
                        selected={selected === viz.id}
                        disabled={isDisabled}
                        onClick={(id) => !isDisabled && onSelect?.(id)}
                    />
                );
            })}
        </div>
    );
}
