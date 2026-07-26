// src/components/Sidebar/VizButton.jsx
//
// One button per visualization mode. Driven entirely by the
// VISUALIZATIONS config so the Sidebar's ~130 lines of copy-paste mode
// buttons (fusion + timelapse rows) collapse to two `.map()`s.

import React from "react";

export default function VizButton({
    viz,
    selected = false,
    disabled = false,
    onClick,
    testId,
}) {
    const cls = [
        "viz-btn",
        selected ? "viz-btn--selected" : "",
        disabled ? "viz-btn--disabled" : "",
    ].filter(Boolean).join(" ");
    return (
        <button
            type="button"
            className={cls}
            onClick={() => onClick?.(viz.id)}
            disabled={disabled}
            aria-pressed={selected}
            aria-label={`${viz.label} (${viz.sub})`}
            data-testid={testId || `viz-${viz.id}`}
            style={{
                position: "relative",
                overflow: "hidden",
                padding: "8px",
                ...(selected ? { "--accent-from": viz.accent?.[0], "--accent-to": viz.accent?.[1] } : {}),
            }}
        >
            <span className="viz-btn__icon" aria-hidden="true" style={{ fontSize: "1rem" }}>{viz.icon}</span>
            <span className="viz-btn__label" style={{ minWidth: 0, flex: 1 }}>
                <span className="viz-btn__title" style={{ fontSize: "0.78rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{viz.label}</span>
                <span className="viz-btn__sub" style={{ fontSize: "0.65rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{viz.sub}</span>
            </span>
            {viz.provenanceBadge && (
                <span
                    className="viz-btn__provenance"
                    title={viz.citation || "Scientific Provenance"}
                    style={{
                        position: "absolute",
                        top: "4px",
                        right: "4px",
                        fontSize: "8px",
                        padding: "1px 3px",
                        borderRadius: "3px",
                        lineHeight: 1,
                        backgroundColor: viz.provenance === "measured" ? "rgba(16, 185, 129, 0.25)" : viz.provenance === "modeled" ? "rgba(56, 189, 248, 0.25)" : "rgba(244, 63, 94, 0.25)",
                        color: viz.provenance === "measured" ? "#34d399" : viz.provenance === "modeled" ? "#38bdf8" : "#fb7185",
                        border: `1px solid ${viz.provenance === "measured" ? "rgba(16, 185, 129, 0.4)" : viz.provenance === "modeled" ? "rgba(56, 189, 248, 0.4)" : "rgba(244, 63, 94, 0.4)"}`,
                    }}
                >
                    {viz.provenanceBadge}
                </span>
            )}
        </button>
    );
}
