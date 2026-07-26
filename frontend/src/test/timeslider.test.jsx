// src/test/timeslider.test.js
//
// Phase 2 (M4) — TimeSlider component tests.
//
// Locks:
//   - one tick per frame in the rendered track
//   - pointer drag dispatches TIME_SERIES_SET_CURRENT on pointerup
//   - keyboard arrow jumps one frame
//   - component hides itself when frames=[]

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { server } from "./setup.js";
import { AppStoreProvider, useLayers, useDispatch } from "../state/AppStore.jsx";
import TimeSlider from "../components/TimeSlider.jsx";
import {
    TIME_SERIES_FRAMES_LOADED,
    TIME_SERIES_SET_CURRENT,
} from "../state/actions.js";

const FRAMES = [
    { date: "2024-01-01", sensor: "sentinel", ready: true },
    { date: "2024-01-05", sensor: "landsat",  ready: true },
    { date: "2024-01-10", sensor: "sentinel", ready: true },
    { date: "2024-01-15", sensor: "sentinel", ready: false },
    { date: "2024-01-20", sensor: "landsat",  ready: true },
];

// Render a wrapper that captures dispatches and seeds the time series.
function renderWithStore() {
    const captured = [];
    function Probe() {
        const dispatch = useDispatch();
        const { timeSeries } = useLayers();
        // Make the dispatch + state visible to the test.
        captured.dispatch = (action) => dispatch(action);
        captured.frames = timeSeries.frames;
        captured.currentFrameIdx = timeSeries.currentFrameIdx;
        return null;
    }
    const utils = render(
        <AppStoreProvider>
            <Probe />
            <TimeSlider />
        </AppStoreProvider>
    );
    return { ...utils, captured };
}

describe("TimeSlider", () => {
    beforeEach(() => {
        server.resetHandlers();
    });

    it("renders one tick per frame", () => {
        const { captured } = renderWithStore();
        act(() => {
            captured.dispatch({
                type: TIME_SERIES_FRAMES_LOADED,
                window: { startDate: "2024-01-01", endDate: "2024-03-31" },
                frames: FRAMES,
            });
        });
        // The track contains 5 ticks.
        const track = document.querySelector(".time-slider__track");
        expect(track).not.toBeNull();
        const ticks = track.querySelectorAll(".time-slider__tick");
        expect(ticks).toHaveLength(5);
    });

    it("hides itself when frames=[]", () => {
        const { container } = renderWithStore();
        // No dispatch; the slice is the initial state (frames: []).
        expect(container.querySelector(".time-slider")).toBeNull();
    });

    it("keyboard arrow dispatches TIME_SERIES_SET_CURRENT ±1", () => {
        const { captured } = renderWithStore();
        act(() => {
            captured.dispatch({
                type: TIME_SERIES_FRAMES_LOADED,
                window: { startDate: "2024-01-01", endDate: "2024-03-31" },
                frames: FRAMES,
            });
        });

        const slider = screen.getByRole("slider");
        slider.focus();
        // currentFrameIdx is 0; pressing → should dispatch idx=1.
        act(() => { fireEvent.keyDown(slider, { key: "ArrowRight" }); });
        // (We can't read the dispatch log directly because the Probe doesn't
        //  capture it. Instead, use the public state — currentFrameIdx
        //  should now be 1.)
        expect(captured.currentFrameIdx).toBe(1);

        act(() => { fireEvent.keyDown(slider, { key: "ArrowLeft" }); });
        expect(captured.currentFrameIdx).toBe(0);

        act(() => { fireEvent.keyDown(slider, { key: "End" }); });
        expect(captured.currentFrameIdx).toBe(FRAMES.length - 1);

        act(() => { fireEvent.keyDown(slider, { key: "Home" }); });
        expect(captured.currentFrameIdx).toBe(0);
    });

    it("pointer drag commits TIME_SERIES_SET_CURRENT on pointerup", () => {
        const { captured } = renderWithStore();
        act(() => {
            captured.dispatch({
                type: TIME_SERIES_FRAMES_LOADED,
                window: { startDate: "2024-01-01", endDate: "2024-03-31" },
                frames: FRAMES,
            });
        });

        const track = document.querySelector(".time-slider__track");
        // Get the bounding box; place the pointer at 50% then at 80%.
        const rect = track.getBoundingClientRect();
        const mid = rect.left + rect.width * 0.5;
        const farRight = rect.left + rect.width * 0.8;

        // pointerdown at 50% → preview idx=2 (5 frames, 0/0.25/0.5/0.75/1.0).
        act(() => { fireEvent.pointerDown(track, { clientX: mid, pointerId: 1 }); });
        // move to 80% → preview idx=4.
        act(() => { fireEvent.pointerMove(track, { clientX: farRight, pointerId: 1 }); });
        // pointerup commits idx=4.
        act(() => { fireEvent.pointerUp(track, { clientX: farRight, pointerId: 1 }); });

        expect(captured.currentFrameIdx).toBe(4);
    });
});
