// src/components/Loader.jsx
//
// M9 — replaces the M8a bouncing-logo-only loader with a full-screen
// overlay that includes an indeterminate progress bar (CSS keyframe).
// Why: the GEE request can take 5–20s. A spinning logo without a
// progress affordance reads as "stuck". The bar doesn't claim a
// percentage — just signals "still working" — but the human eye
// reads it as progress because the bar moves linearly.

import { useEffect, useState } from "react";

export default function Loader({ isLoading }) {
    const [shouldRender, setShouldRender] = useState(isLoading);

    useEffect(() => {
        if (isLoading) {
            setShouldRender(true);
            return;
        }
        // Delay unmount for fade-out animation.
        const t = setTimeout(() => setShouldRender(false), 350);
        return () => clearTimeout(t);
    }, [isLoading]);

    if (!shouldRender) return null;

    return (
        <div
            className={`loader-screen ${isLoading ? "is-loading" : "is-fading"}`}
            aria-live="polite"
            aria-busy={isLoading}
            role="status"
        >
            <div className="loader-stack">
                <div className="loader-orbit" aria-hidden="true">
                    <div className="loader-orbit__core">🛰️</div>
                    <div className="loader-orbit__ring loader-orbit__ring--1" />
                    <div className="loader-orbit__ring loader-orbit__ring--2" />
                    <div className="loader-orbit__ring loader-orbit__ring--3" />
                </div>

                <div className="loader-bar" aria-hidden="true">
                    <div className="loader-bar__fill" />
                </div>

                <p className="loader-text">Loading satellite data…</p>
            </div>
        </div>
    );
}
