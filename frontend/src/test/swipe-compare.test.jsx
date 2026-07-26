// src/test/swipe-compare.test.js
//
// Phase 2 (M5) — SwipeCompare component tests.
//
// Locks:
//   - SwipeCompare renders nothing when compare.enabled is false
//   - SwipeCompare renders nothing when frames.length < 2
//   - divider drag dispatches COMPARE_DIVIDER_MOVED with the new x
//   - slot pickers (slotA / slotB) dispatch COMPARE_SLOT_CHANGED
//   - divider keyboard arrow nudges x by ±0.02 (or ±0.10 with shift)

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { server } from "./setup.js";
import { AppStoreProvider, useDispatch, useLayers } from "../state/AppStore.jsx";
import SwipeCompare from "../components/SwipeCompare.jsx";
import {
    COMPARE_TOGGLED,
    COMPARE_SLOT_CHANGED,
    COMPARE_DIVIDER_MOVED,
    TIME_SERIES_FRAMES_LOADED,
} from "../state/actions.js";

const FRAMES = [
    { date: "2024-01-01", sensor: "sentinel", ready: true, fusionId: "f1", tileUrl: "https://x/1/{z}/{x}/{y}" },
    { date: "2024-01-05", sensor: "landsat",  ready: true, fusionId: "f2", tileUrl: "https://x/2/{z}/{x}/{y}" },
    { date: "2024-01-10", sensor: "sentinel", ready: true, fusionId: "f3", tileUrl: "https://x/3/{z}/{x}/{y}" },
];

// A wrapper that captures dispatched actions + exposes state.
function renderWithStore() {
    const captured = { actions: [] };
    function Probe() {
        const dispatch = useDispatch();
        const { compare, timeSeries } = useLayers();
        captured.dispatch = (a) => dispatch(a);
        captured.compare = compare;
        captured.timeSeries = timeSeries;
        return null;
    }
    const utils = render(
        <AppStoreProvider>
            <Probe />
            <SwipeCompare />
        </AppStoreProvider>
    );
    return { ...utils, captured };
}

function seedFramesAndEnableCompare(captured) {
    act(() => {
        captured.dispatch({
            type: TIME_SERIES_FRAMES_LOADED,
            window: { startDate: "2024-01-01", endDate: "2024-03-31" },
            frames: FRAMES,
        });
        captured.dispatch({ type: COMPARE_TOGGLED, enabled: true });
    });
}

describe("SwipeCompare", () => {
    beforeEach(() => {
        server.resetHandlers();
    });

    it("renders nothing when compare is disabled", () => {
        const { container } = renderWithStore();
        // No divider, no badges.
        expect(container.querySelector(".swipe-compare__divider")).toBeNull();
        expect(container.querySelector(".swipe-compare__badge")).toBeNull();
    });

    it("renders nothing when frames < 2", () => {
        const { captured, container } = renderWithStore();
        act(() => {
            captured.dispatch({
                type: TIME_SERIES_FRAMES_LOADED,
                window: { startDate: "2024-01-01", endDate: "2024-03-31" },
                frames: [FRAMES[0]], // only 1
            });
            captured.dispatch({ type: COMPARE_TOGGLED, enabled: true });
        });
        // The reducer ignores the toggle ON with <2 frames; verify by
        // checking the divider didn't render.
        expect(container.querySelector(".swipe-compare__divider")).toBeNull();
    });

    it("renders divider + badges when compare is enabled and ≥2 frames", () => {
        const { captured, container } = renderWithStore();
        seedFramesAndEnableCompare(captured);
        const divider = container.querySelector(".swipe-compare__divider");
        const badges = container.querySelectorAll(".swipe-compare__badge");
        expect(divider).not.toBeNull();
        expect(badges).toHaveLength(2);
        // A · 2024-01-01 · sentinel   /   B · 2024-01-05 · landsat
        expect(badges[0].textContent).toMatch(/2024-01-01/);
        expect(badges[0].textContent).toMatch(/sentinel/);
        expect(badges[1].textContent).toMatch(/2024-01-05/);
        expect(badges[1].textContent).toMatch(/landsat/);
    });

    it("pointer drag dispatches COMPARE_DIVIDER_MOVED", () => {
        const { captured, container } = renderWithStore();
        seedFramesAndEnableCompare(captured);
        const divider = container.querySelector(".swipe-compare__divider");
        const rect = divider.getBoundingClientRect();

        // pointerdown at the left edge (x=0); pointermove to 80%.
        act(() => {
            fireEvent.pointerDown(divider, { clientX: rect.left, pointerId: 1 });
        });
        act(() => {
            fireEvent.pointerMove(divider, { clientX: rect.left + rect.width * 0.8, pointerId: 1 });
        });
        act(() => {
            fireEvent.pointerUp(divider, { clientX: rect.left + rect.width * 0.8, pointerId: 1 });
        });
        // The reducer's COMPARE_DIVIDER_MOVED clamps to [0, 1].
        expect(captured.compare.dividerX).toBeCloseTo(0.8, 1);
    });

    it("keyboard arrow on the divider nudges dividerX by 0.02", () => {
        const { captured, container } = renderWithStore();
        seedFramesAndEnableCompare(captured);
        const divider = container.querySelector(".swipe-compare__divider");
        divider.focus();
        // Initial dividerX is 0.5.
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight" }); });
        expect(captured.compare.dividerX).toBeCloseTo(0.52, 2);
        act(() => { fireEvent.keyDown(divider, { key: "ArrowLeft" }); });
        expect(captured.compare.dividerX).toBeCloseTo(0.50, 2);
    });

    it("shift+arrow nudges dividerX by 0.10", () => {
        const { captured, container } = renderWithStore();
        seedFramesAndEnableCompare(captured);
        const divider = container.querySelector(".swipe-compare__divider");
        divider.focus();
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight", shiftKey: true }); });
        expect(captured.compare.dividerX).toBeCloseTo(0.60, 2);
        // Clamps at 1.0.
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight", shiftKey: true }); });
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight", shiftKey: true }); });
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight", shiftKey: true }); });
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight", shiftKey: true }); });
        act(() => { fireEvent.keyDown(divider, { key: "ArrowRight", shiftKey: true }); });
        expect(captured.compare.dividerX).toBe(1);
    });

    it("dispatching COMPARE_SLOT_CHANGED updates slotA / slotB", () => {
        const { captured } = renderWithStore();
        seedFramesAndEnableCompare(captured);
        act(() => { captured.dispatch({ type: COMPARE_SLOT_CHANGED, slot: "A", idx: 2 }); });
        expect(captured.compare.slotA).toBe(2);
        act(() => { captured.dispatch({ type: COMPARE_SLOT_CHANGED, slot: "B", idx: 0 }); });
        expect(captured.compare.slotB).toBe(0);
        // slotA preserved.
        expect(captured.compare.slotA).toBe(2);
    });
});
