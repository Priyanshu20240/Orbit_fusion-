// playwright.config.js — M10 E2E
//
// Non-blocking on push: the main CI workflow runs the unit + integration
// suite but NOT the Playwright job. The E2E job is opt-in via
// `workflow_dispatch` (or by running `npm run e2e` locally) because
// the backend has to be up *and* have live creds for the happy-path
// to mean anything. A green E2E is an explicit operator sign-off that
// the full frontend → backend → GEE stack runs end-to-end.

import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.E2E_PORT || "5173";
const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
    testDir: "./e2e",
    timeout: 30_000,
    expect: { timeout: 5_000 },
    fullyParallel: false,    // single happy-path; concurrency would be silly
    forbidOnly: !!process.env.CI,
    retries: 0,              // don't auto-hide regressions
    workers: 1,
    reporter: process.env.CI ? "github" : "list",
    use: {
        baseURL: BASE,
        trace: "on-first-retry",
        screenshot: "only-on-failure",
    },
    projects: [
        {
            name: "chromium",
            use: { ...devices["Desktop Chrome"] },
        },
    ],
    webServer: {
        // The E2E host boots `npm run preview` (the built artefact),
        // not `npm run dev` — we want to test the same bundle that
        // ships. The backend at :8000 is the operator's responsibility
        // (the workflow's E2E job starts it on the same runner).
        command: "npm run preview -- --host 127.0.0.1 --port " + PORT,
        url: BASE,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
    },
});
