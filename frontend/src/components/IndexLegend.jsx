// src/components/IndexLegend.jsx
//
// M9 — small overlay that shows the color-ramp + value range for the
// active visualization. LST specifically uses °C (20–45) instead of
// 0–1 like the other indices; the config-driven `legend` field on
// each visualization entry carries { min, max, colors, unit }.
//
// `min`/`max` are the range endpoints; the gradient is built from
// the 3-stop palette (`colors[0]` → `colors[1]` → `colors[2]`). The
// label text adapts to the unit (°C vs dimensionless).

import { VISUALIZATIONS_BY_ID } from "../config/visualizations.js";

function gradientCss(colors) {
    if (!colors || colors.length < 2) return "linear-gradient(90deg, #ccc, #fff)";
    const stops = colors.length === 2
        ? `${colors[0]} 0%, ${colors[1]} 100%`
        : `${colors[0]} 0%, ${colors[1]} 50%, ${colors[2]} 100%`;
    return `linear-gradient(90deg, ${stops})`;
}

function formatVal(v, unit) {
    if (unit === "°C") return `${Math.round(v)}°C`;
    return v.toFixed(1);
}

export default function IndexLegend({ mode }) {
    const viz = VISUALIZATIONS_BY_ID[mode];
    if (!viz || !viz.legend) return null;
    const { min, max, colors, unit } = viz.legend;

    return (
        <div className="index-legend" role="figure" aria-label={`${viz.label} value range`}>
            <div className="index-legend__title">
                <span aria-hidden="true">{viz.icon}</span>
                <span>{viz.label}</span>
            </div>
            <div
                className="index-legend__bar"
                style={{ background: gradientCss(colors) }}
                aria-hidden="true"
            />
            <div className="index-legend__scale">
                <span>{formatVal(min, unit)}</span>
                <span>{formatVal(max, unit)}</span>
            </div>
        </div>
    );
}
