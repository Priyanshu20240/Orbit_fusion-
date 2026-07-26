// src/test/handlers.js
//
// MSW handlers for the M8a+M8b frontend tests. Handlers target the M7
// backend contract (tile_url_template, bounds, expires_at, scene_counts,
// max_native_zoom, mapid, fusion_id) so tests assert against the *real*
// wire shape — not a frontend-invented one.
//
// Why MSW: vitest can't hit a real backend (no GEE, no live network),
// and patching fetch with a manual mock is fragile. MSW intercepts
// at the network layer so the production api/client.js code is what
// runs end-to-end inside the test.

import { http, HttpResponse, delay } from "msw";

/**
 * `/api/fusion/gee-harmonize` — variable delay so the click-race test can
 * fire NDVI (slow) then true_color (fast) and observe only true_color
 * sticks (AbortController cancels the in-flight slow request).
 *
 * `delayMs` defaults to 0 (immediate) so most tests don't see the
 * ordering effect. The click-race test sets `?delayMs=200` to force a
 * slow response for NDVI and `?delayMs=0` for true_color.
 */
export const fusionHandler = http.post(
    "/api/fusion/gee-harmonize",
    async ({ request }) => {
        const body = await request.json();
        const url = new URL(request.url);
        const delayMs = Number(url.searchParams.get("delayMs") || "0");
        if (delayMs > 0) await delay(delayMs);

        // The contract is checked by the backend; for tests we just
        // stamp the visualization into the response so the test can
        // assert on it.
        const fusion_id = `f-${body.visualization}-${Math.random().toString(16).slice(2, 8)}`;
        return HttpResponse.json({
            fusion_id,
            tile_url_template: `https://earthengine.example/v1/${fusion_id}/tiles/{z}/{x}/{y}`,
            bounds: body.bounds ? [
                [body.bounds[1], body.bounds[0]],
                [body.bounds[3], body.bounds[2]],
            ] : null,
            visualization: body.visualization,
            scene_counts: { sentinel: 3, landsat: 2 },
            expires_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
            max_native_zoom: 14,
            mapid: fusion_id,
        });
    }
);

/** `/api/fusion/{fusion_id}/refresh-mapid` — happy path. */
export const refreshHandler = http.get(
    "/api/fusion/:fusion_id/refresh-mapid",
    async ({ params }) => {
        const { fusion_id } = params;
        return HttpResponse.json({
            fusion_id,
            tile_url_template: `https://earthengine.example/v1/${fusion_id}/tiles/{z}/{x}/{y}?refreshed=1`,
            mapid: fusion_id,
            expires_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
            max_native_zoom: 14,
        });
    }
);

/** `/api/search/all` — empty success. */
export const searchAllHandler = http.post("/api/search/all", () =>
    HttpResponse.json({
        sentinel: { satellite: "Sentinel-2", total_results: 0, scenes: [] },
        landsat: { satellite: "Landsat-8/9", total_results: 0, scenes: [] },
        bhuvan: { satellite: "ISRO", layers: {} },
    })
);

/**
 * `/api/scenes/overlap` — Phase 2 per-scene date list. Variable delay
 * so the timeseries test can verify abort-on-redispatch.
 *
 * Default payload: 3 S2 frames + 1 L8 frame. The test can pass
 * `?count=N&delayMs=N` to control the scene count and latency.
 */
export const overlapHandler = http.post(
    "/api/scenes/overlap",
    async ({ request }) => {
        const url = new URL(request.url);
        const delayMs = Number(url.searchParams.get("delayMs") || "0");
        const count = Number(url.searchParams.get("count") || "3");
        if (delayMs > 0) await delay(delayMs);

        const frames = [];
        for (let i = 0; i < count; i++) {
            frames.push({
                date: `2024-01-${String(i + 1).padStart(2, "0")}`,
                sensor: i % 2 === 0 ? "sentinel" : "landsat",
                scene_id: `scene-${i}`,
                cloud_cover: 5.0,
            });
        }
        return HttpResponse.json({ frames, bucket: "scene" });
    }
);

/**
 * `/api/fusion/timelapse` — Phase 0 endpoint, re-plumbed in M6. The MSW
 * handler echoes the request body back as a synthetic success response.
 */
export const timelapseHandler = http.post(
    "/api/fusion/timelapse",
    async ({ request }) => {
        const body = await request.json();
        return HttpResponse.json({
            success: true,
            url: "https://earthengine.example/v1/timelapse/abc.gif",
            count: 12,
            echo: body,
        });
    }
);

export const handlers = [fusionHandler, refreshHandler, searchAllHandler, overlapHandler, timelapseHandler];
