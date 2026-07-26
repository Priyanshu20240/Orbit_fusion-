// src/test/click-race.test.js
//
// The spec's "highest-value test" (design §C.4):
//   click NDVI (slow) then true_color (fast);
//   after both resolve, the active layer is the fast one (true_color),
//   not the slow one (NDVI). This proves the AbortController race-fix
//   in useFusion actually works.
//
// MSW is set up in src/test/setup.js. The fusionHandler supports a
// `?delayMs=` query param so we can make the first request slow.

import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { server } from "./setup.js";
import { useFusion } from "../hooks/useFusion.js";

const AOI = {
    min_lon: 77.55,
    min_lat: 12.95,
    max_lon: 77.62,
    max_lat: 13.02,
};

const dateRange = { startDate: "2024-01-01", endDate: "2024-03-31" };
const activeSatellites = { sentinel: true, landsat: true, bhuvan: false };

// Re-render the hook fresh for each test (no shared state).
function mountFusion(opts = {}) {
    return renderHook(
        ({ onLayer, onStatusChange }) =>
            useFusion({
                aoi: AOI,
                dateRange,
                activeSatellites,
                onLayer,
                onStatusChange,
                ...opts,
            }),
        { initialProps: { onLayer: undefined, onStatusChange: undefined } }
    );
}

describe("useFusion — click race", () => {
    beforeEach(() => {
        // Reset any handler overrides from the previous test.
        server.resetHandlers();
    });

    it("only the last-clicked mode sticks when NDVI (slow) is followed by true_color (fast)", async () => {
        // Override the default handler: make NDVI slow, true_color fast.
        server.use(
            http.post("/api/fusion/gee-harmonize", async ({ request }) => {
                const body = await request.json();
                const slow = body.visualization === "ndvi";
                if (slow) await delay(200);
                return HttpResponse.json({
                    fusion_id: `f-${body.visualization}`,
                    tile_url_template: `https://example/v1/${body.visualization}/tiles/{z}/{x}/{y}`,
                    bounds: [
                        [AOI.min_lat, AOI.min_lon],
                        [AOI.max_lat, AOI.max_lon],
                    ],
                    visualization: body.visualization,
                    scene_counts: { sentinel: 3, landsat: 2 },
                    expires_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
                    max_native_zoom: 14,
                    mapid: `f-${body.visualization}`,
                });
            })
        );

        const layers = [];
        const hook = mountFusion({ onLayer: (l) => layers.push(l) });

        // Click NDVI first.
        await act(async () => {
            hook.result.current.run("ndvi");
            // Yield once so the request is in flight.
            await new Promise((r) => setTimeout(r, 20));
        });

        // Click true_color before NDVI resolves.
        await act(async () => {
            hook.result.current.run("true_color");
            // Wait for true_color's promise (fast) to settle.
            await new Promise((r) => setTimeout(r, 30));
        });

        // The first layer pushed must be the FAST one.
        // (If the race-fix is broken, NDVI's slow response lands second
        // and overwrites true_color — and the test fails.)
        expect(layers.length).toBe(1);
        expect(layers[0].mode).toBe("true_color");
        expect(layers[0].id).toBe("gee-fusion-f-true_color");

        // Now wait for NDVI's slow response to land. It should be
        // aborted by the controller; the catch path swallows AbortError
        // silently and the layer is not pushed.
        await act(async () => {
            await new Promise((r) => setTimeout(r, 250));
        });

        // Still only one layer.
        expect(layers.length).toBe(1);
        expect(layers[0].mode).toBe("true_color");
    });

    it("status transitions to success on a clean fusion", async () => {
        const statuses = [];
        const hook = mountFusion({ onStatusChange: (s) => statuses.push(s) });

        await act(async () => {
            await hook.result.current.run("ndvi");
        });

        // We expect: loading → success.
        expect(statuses).toContain("loading");
        expect(statuses).toContain("success");
        // The hook returns the layer too.
        expect(hook.result.current.layer).toBeTruthy();
        expect(hook.result.current.layer.mode).toBe("ndvi");
    });

    // ────────────────────────────────────────────────────────────────────
    // Phase 1 (M6): the click-race is mode-agnostic — the AbortController
    // works for any visualization. Test it with a Phase 1 mode to lock the
    // contract for the new strategies.
    // ────────────────────────────────────────────────────────────────────
    it("click-race works for Phase 1 `harmonized_l8` (slow) + `gap_fill` (fast)", async () => {
        server.use(
            http.post("/api/fusion/gee-harmonize", async ({ request }) => {
                const body = await request.json();
                const slow = body.visualization === "harmonized_l8";
                if (slow) await delay(200);
                return HttpResponse.json({
                    fusion_id: `f-${body.visualization}`,
                    tile_url_template: `https://example/v1/${body.visualization}/tiles/{z}/{x}/{y}`,
                    bounds: [
                        [AOI.min_lat, AOI.min_lon],
                        [AOI.max_lat, AOI.max_lon],
                    ],
                    visualization: body.visualization,
                    scene_counts: { sentinel: 4, landsat: 2 },
                    expires_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
                    max_native_zoom: 14,
                    mapid: `f-${body.visualization}`,
                });
            })
        );

        const layers = [];
        const hook = mountFusion({ onLayer: (l) => layers.push(l) });

        // Click harmonized_l8 first (slow).
        await act(async () => {
            hook.result.current.run("harmonized_l8");
            await new Promise((r) => setTimeout(r, 20));
        });

        // Click gap_fill before harmonized_l8 resolves.
        await act(async () => {
            hook.result.current.run("gap_fill");
            await new Promise((r) => setTimeout(r, 30));
        });

        // Only the FAST (gap_fill) layer lands. The slow harmonized_l8 is aborted.
        expect(layers.length).toBe(1);
        expect(layers[0].mode).toBe("gap_fill");
        expect(layers[0].id).toBe("gee-fusion-f-gap_fill");
    });

    it("status transitions to success for `real_lst` (Landsat-only mode)", async () => {
        // real_lst has `sensors: ["landsat"]` only — the hook's `activeSatellites`
        // filter in the test fixture is `{ sentinel: true, landsat: true }`,
        // which means real_lst is allowed.
        const statuses = [];
        const hook = mountFusion({ onStatusChange: (s) => statuses.push(s) });

        await act(async () => {
            await hook.result.current.run("real_lst");
        });

        expect(statuses).toContain("loading");
        expect(statuses).toContain("success");
        expect(hook.result.current.layer).toBeTruthy();
        expect(hook.result.current.layer.mode).toBe("real_lst");
    });
});
