// src/components/BasemapControl.jsx
//
// M9 — radiogroup-style basemap switcher. Reads from config/basemaps.js
// and the basemapId slice of the store. a11y: role="radiogroup" with
// role="radio" + aria-checked on each button.

import { BASEMAPS } from "../config/basemaps.js";

export default function BasemapControl({ value, onChange }) {
    return (
        <div
            className="basemap-control"
            role="radiogroup"
            aria-label="Basemap"
        >
            {BASEMAPS.map((b) => {
                const selected = value === b.id;
                return (
                    <button
                        key={b.id}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        className={`basemap-btn ${selected ? "basemap-btn--selected" : ""}`}
                        onClick={() => onChange?.(b.id)}
                        data-testid={`basemap-${b.id}`}
                    >
                        {b.label}
                    </button>
                );
            })}
        </div>
    );
}
