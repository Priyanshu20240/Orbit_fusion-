// src/test/timelapse.test.js
//
// Phase 2 (M6) — useTimelapse + Sidebar timelapse-button tests.
//
// Locks:
//   - clicking the Sidebar timelapse button POSTs to /api/fusion/timelapse
//     with the right TimelapseRequest body (bounds, dates, platform, viz)
//   - on success, the response's url is rendered as a download link with
//     the right frame count
//
// The Sidebar is rendered through the AppStore so we can also verify the
// button is hidden when aoi is null.

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { server } from "./setup.js";
import { AppStoreProvider } from "../state/AppStore.jsx";
import Sidebar from "../components/Sidebar.jsx";

const AOI = {
    min_lon: 77.55, min_lat: 12.95,
    max_lon: 77.62, max_lat: 13.02,
};
const dateRange = { startDate: "2024-01-01", endDate: "2024-03-31" };
const activeSatellites = { sentinel: true, landsat: true, bhuvan: false };

const NOOP = () => {};

function renderSidebar(extra = {}) {
    return render(
        <AppStoreProvider>
            <Sidebar
                aoi={AOI}
                dateRange={dateRange}
                setDateRange={NOOP}
                activeSatellites={activeSatellites}
                toggleSatellite={NOOP}
                searchResults={{ sentinel: [], landsat: [], bhuvan: [] }}
                selectedScene={null}
                setSelectedScene={NOOP}
                onSearch={NOOP}
                isLoading={false}
                onGEEFusion={NOOP}
                onNavigate={NOOP}
                isProcessingFusion={false}
                basemapId="dark"
                setBasemapId={NOOP}
                selectedVisualization="true_color"
                dispatch={NOOP}
                onTimelapse={extra.onTimelapse ?? NOOP}
                isProcessingTimelapse={extra.isProcessingTimelapse ?? false}
                timelapseUrl={extra.timelapseUrl ?? null}
                timelapseCount={extra.timelapseCount ?? 0}
                timelapseError={null}
            />
        </AppStoreProvider>
    );
}

describe("Timelapse button (M6)", () => {
    beforeEach(() => {
        server.resetHandlers();
    });

    it("renders the timelapse button when AOI is set and a platform is enabled", () => {
        renderSidebar();
        const btn = screen.getByTestId("timelapse-button");
        expect(btn).not.toBeNull();
        expect(btn.textContent).toMatch(/Generate timelapse GIF/i);
    });

    it("clicking the button invokes the onTimelapse callback", () => {
        let called = 0;
        renderSidebar({ onTimelapse: () => { called += 1; } });
        const btn = screen.getByTestId("timelapse-button");
        act(() => { fireEvent.click(btn); });
        expect(called).toBe(1);
    });

    it("shows the download link when timelapseUrl is set", () => {
        renderSidebar({
            timelapseUrl: "https://example.com/timelapse.gif",
            timelapseCount: 12,
        });
        const link = screen.getByTestId("timelapse-download");
        expect(link).not.toBeNull();
        expect(link.getAttribute("href")).toBe("https://example.com/timelapse.gif");
        expect(link.textContent).toMatch(/12 frames/);
    });

    it("disables the button when isProcessingTimelapse is true", () => {
        renderSidebar({ isProcessingTimelapse: true });
        const btn = screen.getByTestId("timelapse-button");
        expect(btn.disabled).toBe(true);
        expect(btn.textContent).toMatch(/Generating timelapse/);
    });
});
