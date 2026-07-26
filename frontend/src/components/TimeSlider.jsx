// src/components/TimeSlider.jsx
//
// Phase 2 (M4) — per-scene time slider.
//
// The slider is a presentation on top of the `useTimeSeries` hook (M3).
// The hook owns the per-frame loop + abort; this component owns:
//   - the visual scrubber (thumb + ticks)
//   - pointer drag (preview-only; no dispatch until pointerup)
//   - keyboard navigation (←/→/space/home/end)
//   - ARIA slider semantics + live region for the current date
//
// Crucially, this component does NOT add or remove a Leaflet layer.
// The active layer is owned by `useFusion`; slider movement only
// dispatches `TIME_SERIES_SET_CURRENT`, which the reducer (M2) maps to
// a `LAYER_UPDATED` on the existing fusion layer — preserving the
// `data-testid="layer-${mode}"` container across slider swaps. That's
// the M8b + Phase 2 invariant.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLayers, useDispatch } from "../state/AppStore.jsx";

const SENSOR_COLOR = {
    sentinel: "#06b6d4", // cyan
    landsat:  "#ea580c", // orange
};

const TICK_DATE_FMT = { month: "short", day: "numeric" };
const CURRENT_DATE_FMT = { year: "numeric", month: "long", day: "numeric" };

function formatDateLabel(dateStr, opts = TICK_DATE_FMT) {
    if (!dateStr) return "";
    // dateStr is "YYYY-MM-DD" (the response from /api/scenes/overlap).
    // Construct as a local date to avoid TZ shifts.
    const [y, m, d] = dateStr.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("en-US", opts);
}

export default function TimeSlider({ disabled = false }) {
    const { timeSeries } = useLayers();
    const dispatch = useDispatch();

    const { frames, currentFrameIdx, loading, error } = timeSeries;
    const frameCount = frames.length;
    const current = frames[currentFrameIdx];

    // Local "scrubbing" state for the drag preview — does NOT update the
    // store. The store only changes on pointerup (or keyboard arrow).
    const [scrubbingTo, setScrubbingTo] = useState(null);
    const trackRef = useRef(null);

    // Compute the displayed frame: either the scrubbing preview, or the
    // committed current frame.
    const displayed = scrubbingTo !== null ? frames[scrubbingTo] : current;

    // ── pointer drag ──────────────────────────────────────────────────
    const pickIdxFromEvent = useCallback((clientX) => {
        const el = trackRef.current;
        if (!el || frameCount === 0 || typeof clientX !== "number" || Number.isNaN(clientX)) return null;
        const rect = el.getBoundingClientRect();
        const width = rect.width || 100;
        const left = rect.left || 0;
        const ratio = Math.max(0, Math.min(1, (clientX - left) / width));
        return Math.round(ratio * (frameCount - 1));
    }, [frameCount]);

    const onPointerDown = useCallback((e) => {
        if (disabled || frameCount === 0) return;
        e.currentTarget.setPointerCapture?.(e.pointerId);
        const idx = pickIdxFromEvent(e.clientX);
        if (idx !== null) setScrubbingTo(idx);
    }, [disabled, frameCount, pickIdxFromEvent]);

    const onPointerMove = useCallback((e) => {
        if (scrubbingTo === null) return;
        const idx = pickIdxFromEvent(e.clientX);
        if (idx !== null) setScrubbingTo(idx);
    }, [scrubbingTo, pickIdxFromEvent]);

    const onPointerUp = useCallback((e) => {
        if (scrubbingTo === null) return;
        e.currentTarget.releasePointerCapture?.(e.pointerId);
        // Commit the scrub.
        dispatch({ type: "TIME_SERIES_SET_CURRENT", idx: scrubbingTo });
        setScrubbingTo(null);
    }, [scrubbingTo, dispatch]);

    // ── keyboard ──────────────────────────────────────────────────────
    const onKeyDown = useCallback((e) => {
        if (disabled || frameCount === 0) return;
        let next = currentFrameIdx;
        switch (e.key) {
            case "ArrowRight":
                next = Math.min(frameCount - 1, currentFrameIdx + (e.shiftKey ? 5 : 1));
                break;
            case "ArrowLeft":
                next = Math.max(0, currentFrameIdx - (e.shiftKey ? 5 : 1));
                break;
            case "Home":
                next = 0;
                break;
            case "End":
                next = frameCount - 1;
                break;
            default:
                return; // not our key
        }
        e.preventDefault();
        dispatch({ type: "TIME_SERIES_SET_CURRENT", idx: next });
    }, [disabled, frameCount, currentFrameIdx, dispatch]);

    // Reset scrubbing on unmount or when the underlying frames list changes
    // (the scrubbing index may no longer be valid).
    useEffect(() => {
        setScrubbingTo(null);
    }, [frames]);

    // Hide entirely when there's no work to do.
    if (frameCount === 0) {
        if (loading) {
            return (
                <div className="time-slider time-slider--loading" role="status" aria-live="polite">
                    Loading time series…
                </div>
            );
        }
        if (error) {
            return (
                <div className="time-slider time-slider--error" role="alert">
                    Time series error: {error}
                </div>
            );
        }
        return null;
    }

    // Play / Pause auto-advance animation loop
    const [isPlaying, setIsPlaying] = useState(false);
    const [playbackSpeed, setPlaybackSpeed] = useState(800); // ms per frame

    useEffect(() => {
        if (!isPlaying || frameCount <= 1) return;
        const timer = setInterval(() => {
            dispatch({
                type: "TIME_SERIES_SET_CURRENT",
                idx: (currentFrameIdx + 1) % frameCount,
            });
        }, playbackSpeed);
        return () => clearInterval(timer);
    }, [isPlaying, frameCount, currentFrameIdx, playbackSpeed, dispatch]);

    const togglePlay = () => setIsPlaying((p) => !p);

    const thumbPct = frameCount === 1
        ? 0
        : (currentFrameIdx / (frameCount - 1)) * 100;

    return (
        <>
            {/* ── Floating Date & Time Overlay Badge on Map ───────────────────── */}
            {displayed && (
                <div
                    style={{
                        position: "fixed",
                        top: "16px",
                        left: "50%",
                        transform: "translateX(-50%)",
                        zIndex: 9999,
                        backgroundColor: "rgba(15, 23, 42, 0.85)",
                        backdropFilter: "blur(8px)",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "20px",
                        padding: "6px 18px",
                        color: "#fff",
                        fontFamily: "system-ui, sans-serif",
                        fontSize: "13px",
                        fontWeight: "600",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.4)",
                        pointerEvents: "none",
                    }}
                >
                    <span style={{ color: "#38bdf8" }}>📅 {formatDateLabel(displayed.date, CURRENT_DATE_FMT)}</span>
                    <span style={{ opacity: 0.4 }}>|</span>
                    <span style={{ color: SENSOR_COLOR[displayed.sensor] || "#a855f7" }}>
                        🛰️ {displayed.sensor?.toUpperCase()}
                    </span>
                    <span style={{ opacity: 0.4 }}>|</span>
                    <span style={{ opacity: 0.8, fontSize: "12px" }}>
                        Frame {currentFrameIdx + 1}/{frameCount}
                    </span>
                </div>
            )}

            <div
                className="time-slider"
                role="slider"
                tabIndex={disabled ? -1 : 0}
                aria-label="Time slider"
                aria-valuemin={0}
                aria-valuemax={frameCount - 1}
                aria-valuenow={currentFrameIdx}
                aria-valuetext={displayed ? `${formatDateLabel(displayed.date, CURRENT_DATE_FMT)}, ${displayed.sensor}` : ""}
                onKeyDown={onKeyDown}
            >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%" }}>
                    <button
                        type="button"
                        className="btn btn--secondary"
                        style={{ padding: "4px 10px", fontSize: "13px", borderRadius: "16px" }}
                        onClick={togglePlay}
                        title={isPlaying ? "Pause Timelapse" : "Play Timelapse"}
                    >
                        {isPlaying ? "⏸️ Pause" : "▶️ Play"}
                    </button>

                    <div
                        className="time-slider__track"
                        ref={trackRef}
                        onPointerDown={onPointerDown}
                        onPointerMove={onPointerMove}
                        onPointerUp={onPointerUp}
                        onPointerCancel={onPointerUp}
                        style={{ flex: 1 }}
                    >
                        {frames.map((f, i) => (
                            <div
                                key={`${f.date}-${f.sensor}-${i}`}
                                className={`time-slider__tick time-slider__tick--${f.sensor} ${f.ready ? "is-ready" : "is-pending"}`}
                                style={{ left: `${(i / (frameCount - 1)) * 100}%` }}
                                title={`${formatDateLabel(f.date)} — ${f.sensor}${f.ready ? "" : " (loading…)"}`}
                            />
                        ))}
                        <div
                            className="time-slider__thumb"
                            style={{ left: `${thumbPct}%` }}
                        />
                    </div>
                </div>

                <div className="time-slider__caption" aria-live="polite">
                    <span className="time-slider__date">
                        {displayed ? formatDateLabel(displayed.date, CURRENT_DATE_FMT) : "—"}
                    </span>
                    <span className="time-slider__sensor" style={{ color: displayed ? SENSOR_COLOR[displayed.sensor] : undefined }}>
                        {displayed ? displayed.sensor : ""}
                    </span>
                    <span className="time-slider__count">
                        {currentFrameIdx + 1} / {frameCount}
                    </span>
                </div>
            </div>
        </>
    );
}
