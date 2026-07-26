// src/components/SwipeCompare.jsx
//
// Phase 2 (M5) — swipe compare UI.
//
// This component is **presentation-only**. It renders the vertical divider
// and the A / B badges, and dispatches COMPARE_DIVIDER_MOVED on pointer
// drag. The actual second L.tileLayer for slot B is managed by Map.jsx
// (the same useEffect that handles the active layer) — see Map.jsx for
// the "second tile layer" branch and the clip-path plumbing.
//
// Why split it this way: the second layer needs imperative access to the
// Leaflet map instance, which Map.jsx already owns. SwipeCompare just
// declares "where the divider is" and lets the map effect do the work.

import React, { useCallback, useEffect, useRef } from "react";
import { useLayers, useDispatch } from "../state/AppStore.jsx";

const COMPARE_LAYER_ID = "__swipe_compare_slotB__";

export { COMPARE_LAYER_ID };

export default function SwipeCompare() {
    const { compare, timeSeries } = useLayers();
    const dispatch = useDispatch();

    const { enabled, slotA, slotB, dividerX } = compare;
    const trackRef = useRef(null);
    const draggingRef = useRef(false);

    const pickX = useCallback((clientX) => {
        const el = trackRef.current;
        if (!el || typeof clientX !== "number" || Number.isNaN(clientX)) return null;
        const rect = el.getBoundingClientRect();
        const width = rect.width || 100;
        const left = rect.left || 0;
        return Math.max(0, Math.min(1, (clientX - left) / width));
    }, []);

    const onPointerDown = useCallback((e) => {
        e.currentTarget.setPointerCapture?.(e.pointerId);
        draggingRef.current = true;
        const x = pickX(e.clientX);
        if (x !== null) dispatch({ type: "COMPARE_DIVIDER_MOVED", x });
    }, [pickX, dispatch]);

    const onPointerMove = useCallback((e) => {
        if (!draggingRef.current) return;
        const x = pickX(e.clientX);
        if (x !== null) dispatch({ type: "COMPARE_DIVIDER_MOVED", x });
    }, [pickX, dispatch]);

    const onPointerUp = useCallback(() => {
        draggingRef.current = false;
    }, []);

    const onKeyDown = useCallback((e) => {
        let delta = 0;
        if (e.key === "ArrowLeft") delta = e.shiftKey ? -0.1 : -0.02;
        else if (e.key === "ArrowRight") delta = e.shiftKey ? 0.1 : 0.02;
        else return;
        e.preventDefault();
        const next = Math.max(0, Math.min(1, dividerX + delta));
        dispatch({ type: "COMPARE_DIVIDER_MOVED", x: next });
    }, [dividerX, dispatch]);

    // Don't render anything when compare is off.
    if (!enabled) {
        return null;
    }

    const a = timeSeries.frames[slotA] || timeSeries.frames[0];
    const b = timeSeries.frames[slotB] || timeSeries.frames[1];

    return (
        <>
            {/* The clip-path is applied to slot B's Leaflet container in
                Map.jsx. We render an A / B badge pair so the user knows
                which side is which when the modes differ. */}
            <div className="swipe-compare__badge swipe-compare__badge--a">
                A · {a?.date ?? ""} · {a?.sensor ?? ""}
            </div>
            <div className="swipe-compare__badge swipe-compare__badge--b">
                B · {b?.date ?? ""} · {b?.sensor ?? ""}
            </div>
            <div
                className="swipe-compare__divider"
                ref={trackRef}
                role="separator"
                aria-orientation="vertical"
                aria-valuenow={Math.round(dividerX * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Swipe compare divider"
                tabIndex={0}
                style={{ left: `${dividerX * 100}%` }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerCancel={onPointerUp}
                onKeyDown={onKeyDown}
            />
        </>
    );
}
