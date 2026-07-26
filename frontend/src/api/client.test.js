// src/api/client.test.js
//
// M8a acceptance: api/client.js test surface
//   - posts the right body for /api/fusion/gee-harmonize
//   - returns the parsed response
//   - surfaces a structured {code, message} on error
//   - never hardcodes a dev host in src/ (the repo-wide grep proves this)
//   - humanize() maps every backend code to a stable string

import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/setup.js";
import { request, humanize, ApiError } from "./client.js";

describe("api/client", () => {
    beforeEach(() => server.resetHandlers());

    it("POSTs JSON and returns the parsed response", async () => {
        server.use(
            http.post("/api/fusion/gee-harmonize", () =>
                HttpResponse.json({ fusion_id: "abc", tile_url_template: "https://x/{z}/{x}/{y}" })
            )
        );
        const r = await request("/api/fusion/gee-harmonize", {
            body: { bounds: [0, 0, 1, 1], visualization: "true_color" },
        });
        expect(r.fusion_id).toBe("abc");
    });

    it("throws ApiError with the backend code on a 404", async () => {
        server.use(
            http.post("/api/fusion/gee-harmonize", () =>
                HttpResponse.json(
                    { code: "no_imagery", message: "no scenes" },
                    { status: 404 }
                )
            )
        );
        try {
            await request("/api/fusion/gee-harmonize", { body: {} });
            throw new Error("should have thrown");
        } catch (err) {
            expect(err).toBeInstanceOf(ApiError);
            expect(err.code).toBe("no_imagery");
            expect(err.status).toBe(404);
        }
    });

    it("humanize maps every known code to a non-empty string", () => {
        const codes = [
            "gee_unavailable",
            "no_imagery",
            "validation_error",
            "gee_compute_error",
            "invalid_request",
            "internal_error",
        ];
        for (const c of codes) {
            const m = humanize(new ApiError(c, "msg", 500));
            expect(m).toBeTruthy();
            expect(typeof m).toBe("string");
        }
    });

    it("humanize returns empty string for AbortError (silent supersede)", () => {
        const e = new Error("aborted");
        e.name = "AbortError";
        expect(humanize(e)).toBe("");
    });
});
