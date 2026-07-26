// src/test/reducer.test.js
//
// Phase 2 (M2) — reducer unit tests for the three new state slices:
//   - timeSeries  (per-scene time axis)
//   - compare     (swipe UI)
//   - timelapse   (the re-plumbed timelapse control)
//
// The headline invariant: TIME_SERIES_SET_CURRENT must patch the existing
// active fusion layer in place. The M8b click-race + Phase 2 slider depend
// on the same `data-testid="layer-${mode}"` container surviving a slider
// swap; adding a new layer would break that.
//
// Tests use the bare reducer (not <App />), so we never need MSW or
// React. Pure dispatch → state assertions.

import { describe, it, expect } from "vitest";
import { reducer, initialState } from "../state/reducer.js";
import * as A from "../state/actions.js";

const FUSION_LAYER = {
    id: "gee-fusion-abc123",
    idPrefix: "gee-fusion-",
    name: "🛰️ GEE Fusion (true_color)",
    satellite: "fusion",
    kind: "gee",
    mode: "true_color",
    tileUrl: "https://example/v1/abc/{z}/{x}/{y}",
    fusionId: "abc123",
    expiresAt: 0,
    bounds: [[12.95, 77.55], [13.02, 77.62]],
    maxNativeZoom: 14,
    visible: true,
    opacity: 100,
};

const AOI = {
    min_lon: 77.55, min_lat: 12.95,
    max_lon: 77.62, max_lat: 13.02,
};

const FRAMES = [
    { date: "2024-01-15", sensor: "sentinel", fusionId: "f1", tileUrl: "https://x/1/{z}/{x}/{y}", ready: true },
    { date: "2024-01-20", sensor: "landsat",  fusionId: "f2", tileUrl: "https://x/2/{z}/{x}/{y}", ready: true },
    { date: "2024-01-25", sensor: "sentinel", fusionId: "f3", tileUrl: "https://x/3/{z}/{x}/{y}", ready: true },
];

// ── TIME_SERIES_REQUESTED ──────────────────────────────────────────────
describe("reducer — timeSeries", () => {
    it("TIME_SERIES_REQUESTED sets loading=true and clears error", () => {
        const s0 = { ...initialState, timeSeries: { ...initialState.timeSeries, error: "old" } };
        const s1 = reducer(s0, { type: A.TIME_SERIES_REQUESTED });
        expect(s1.timeSeries.loading).toBe(true);
        expect(s1.timeSeries.error).toBeNull();
    });

    it("TIME_SERIES_FRAMES_LOADED replaces frames + sets source='overlap'", () => {
        const s0 = { ...initialState, timeSeries: { ...initialState.timeSeries, loading: true } };
        const s1 = reducer(s0, {
            type: A.TIME_SERIES_FRAMES_LOADED,
            window: { startDate: "2024-01-01", endDate: "2024-03-31" },
            frames: FRAMES,
        });
        expect(s1.timeSeries.frames).toEqual(FRAMES);
        expect(s1.timeSeries.currentFrameIdx).toBe(0);
        expect(s1.timeSeries.loading).toBe(false);
        expect(s1.timeSeries.source).toBe("overlap");
        expect(s1.timeSeries.window).toEqual({ startDate: "2024-01-01", endDate: "2024-03-31" });
    });

    it("TIME_SERIES_FRAME_READY patches the matching frame in place", () => {
        const s0 = {
            ...initialState,
            timeSeries: { ...initialState.timeSeries, frames: [
                { date: "2024-01-15", sensor: "sentinel", ready: false },
                { date: "2024-01-20", sensor: "landsat",  ready: false },
            ] },
        };
        const s1 = reducer(s0, {
            type: A.TIME_SERIES_FRAME_READY,
            date: "2024-01-15", sensor: "sentinel",
            fusionId: "f1", tileUrl: "https://x/1/{z}/{x}/{y}",
            sceneCounts: { sentinel: 1, landsat: 0 },
        });
        expect(s1.timeSeries.frames[0].ready).toBe(true);
        expect(s1.timeSeries.frames[0].fusionId).toBe("f1");
        expect(s1.timeSeries.frames[0].tileUrl).toBe("https://x/1/{z}/{x}/{y}");
        // The OTHER frame is untouched.
        expect(s1.timeSeries.frames[1].ready).toBe(false);
        expect(s1.timeSeries.frames[1].fusionId).toBeUndefined();
    });

    // The HEADLINE test — the M8b invariant + Phase 2 slider invariant.
    it("TIME_SERIES_SET_CURRENT patches the active layer in place (no new layer)", () => {
        // Start with the active layer in state + 3 frames loaded.
        const s0 = {
            ...initialState,
            layers: [FUSION_LAYER],
            timeSeries: { ...initialState.timeSeries, frames: FRAMES, currentFrameIdx: 0 },
        };
        const s1 = reducer(s0, { type: A.TIME_SERIES_SET_CURRENT, idx: 1 });

        // layers[] length is still 1 (no second layer added)
        expect(s1.layers.length).toBe(1);
        // The same layer id
        expect(s1.layers[0].id).toBe("gee-fusion-abc123");
        // tileUrl + fusionId now match frame idx=1
        expect(s1.layers[0].tileUrl).toBe(FRAMES[1].tileUrl);
        expect(s1.layers[0].fusionId).toBe(FRAMES[1].fusionId);
        // currentFrameIdx advanced
        expect(s1.timeSeries.currentFrameIdx).toBe(1);
    });

    it("TIME_SERIES_CLEAR empties frames and resets compare", () => {
        const s0 = {
            ...initialState,
            timeSeries: { ...initialState.timeSeries, frames: FRAMES, currentFrameIdx: 2 },
            compare: { ...initialState.compare, enabled: true },
        };
        const s1 = reducer(s0, { type: A.TIME_SERIES_CLEAR });
        expect(s1.timeSeries.frames).toEqual([]);
        expect(s1.timeSeries.currentFrameIdx).toBe(0);
        expect(s1.compare.enabled).toBe(false);
    });
});

// ── COMPARE ────────────────────────────────────────────────────────────
describe("reducer — compare", () => {
    it("COMPARE_TOGGLED true is ignored when no frames", () => {
        const s0 = initialState;
        const s1 = reducer(s0, { type: A.COMPARE_TOGGLED, enabled: true });
        // No state change — frames.length < 2 means we can't compare.
        expect(s1.compare.enabled).toBe(false);
    });

    it("COMPARE_TOGGLED true succeeds when ≥2 frames", () => {
        const s0 = { ...initialState, timeSeries: { ...initialState.timeSeries, frames: FRAMES } };
        const s1 = reducer(s0, { type: A.COMPARE_TOGGLED, enabled: true });
        expect(s1.compare.enabled).toBe(true);
    });

    it("COMPARE_SLOT_CHANGED updates slotA / slotB", () => {
        const s0 = { ...initialState, timeSeries: { ...initialState.timeSeries, frames: FRAMES } };
        const sA = reducer(s0, { type: A.COMPARE_SLOT_CHANGED, slot: "A", idx: 2 });
        expect(sA.compare.slotA).toBe(2);
        const sB = reducer(sA, { type: A.COMPARE_SLOT_CHANGED, slot: "B", idx: 0 });
        expect(sB.compare.slotB).toBe(0);
        // slotA is preserved
        expect(sB.compare.slotA).toBe(2);
    });

    it("COMPARE_DIVIDER_MOVED clamps to [0, 1]", () => {
        const sOver = reducer(initialState, { type: A.COMPARE_DIVIDER_MOVED, x: 1.7 });
        expect(sOver.compare.dividerX).toBe(1);
        const sUnder = reducer(initialState, { type: A.COMPARE_DIVIDER_MOVED, x: -0.4 });
        expect(sUnder.compare.dividerX).toBe(0);
        const sMid = reducer(initialState, { type: A.COMPARE_DIVIDER_MOVED, x: 0.42 });
        expect(sMid.compare.dividerX).toBeCloseTo(0.42);
    });
});

// ── TIMELAPSE ──────────────────────────────────────────────────────────
describe("reducer — timelapse", () => {
    it("TIMELAPSE_STARTED sets loading=true, clears error", () => {
        const s0 = { ...initialState, timelapse: { ...initialState.timelapse, error: "old" } };
        const s1 = reducer(s0, { type: A.TIMELAPSE_STARTED });
        expect(s1.timelapse.loading).toBe(true);
        expect(s1.timelapse.error).toBeNull();
    });

    it("TIMELAPSE_SUCCEEDED stores url + count", () => {
        const s1 = reducer(initialState, {
            type: A.TIMELAPSE_SUCCEEDED,
            url: "https://example.com/timelapse.gif",
            count: 12,
        });
        expect(s1.timelapse.url).toBe("https://example.com/timelapse.gif");
        expect(s1.timelapse.count).toBe(12);
        expect(s1.timelapse.loading).toBe(false);
    });

    it("TIMELAPSE_FAILED stores the error", () => {
        const s1 = reducer(initialState, { type: A.TIMELAPSE_FAILED, error: "boom" });
        expect(s1.timelapse.error).toBe("boom");
        expect(s1.timelapse.loading).toBe(false);
    });
});

// ── Reset on AOI change (Phase 2: time axis is window-specific) ────────
describe("reducer — AOI/DATE_RANGE reset the time axis", () => {
    it("AOI_CHANGED resets timeSeries + compare", () => {
        const s0 = {
            ...initialState,
            aoi: null,
            timeSeries: { ...initialState.timeSeries, frames: FRAMES, currentFrameIdx: 1 },
            compare: { ...initialState.compare, enabled: true },
        };
        const s1 = reducer(s0, { type: A.AOI_CHANGED, aoi: AOI });
        expect(s1.timeSeries.frames).toEqual([]);
        expect(s1.compare.enabled).toBe(false);
    });

    it("DATE_RANGE_CHANGED resets timeSeries + compare", () => {
        const s0 = {
            ...initialState,
            timeSeries: { ...initialState.timeSeries, frames: FRAMES },
            compare: { ...initialState.compare, enabled: true },
        };
        const s1 = reducer(s0, {
            type: A.DATE_RANGE_CHANGED,
            patch: { endDate: "2024-06-30" },
        });
        expect(s1.timeSeries.frames).toEqual([]);
        expect(s1.compare.enabled).toBe(false);
        // And the date range was actually updated.
        expect(s1.dateRange.endDate).toBe("2024-06-30");
    });
});
