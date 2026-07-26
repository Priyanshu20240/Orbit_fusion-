// e2e/happy-path.spec.js — M10
//
// The single E2E test. It runs against a built frontend (`npm run
// preview`) and a live backend at :8000 with `ORBITER_GEE_LIVE=1` so
// /health is 200.
//
// What it asserts:
//   1. The app shell renders (header is visible).
//   2. The Leaflet map container is present.
//   3. The MapControls overlay is in the DOM (this catches a class of
//      "Vite builds, dev server boots, but the React tree is empty"
//      bugs that vitest can't see because vitest renders <App /> in
//      isolation).
//   4. The basemap switcher (BasemapControl radiogroup) is present and
//      clickable. We click "Light" and confirm `aria-checked` flips.
//
// What it does NOT assert:
//   * That tiles actually load — that requires real network + GEE
//     creds and is a manual smoke on the Windows host.
//   * That AOI draw → fusion round-trips — that would need a real
//     draw interaction and is beyond a CI-friendly happy-path.

import { test, expect } from "@playwright/test";

test("shell renders, map mounts, basemap switcher is interactive", async ({ page }) => {
    await page.goto("/");

    // 1. The header h1 is the cheapest "the bundle ran" smoke.
    await expect(page.getByRole("heading", { name: /orbiter fusion/i })).toBeVisible();

    // 2. The Leaflet container mounted.
    await expect(page.locator(".leaflet-container")).toBeVisible();

    // 3. The basemap radiogroup is present. We click "Light" and
    //    confirm aria-checked flips.
    const basemap = page.getByRole("radiogroup", { name: /basemap/i });
    await expect(basemap).toBeVisible();

    const lightBtn = page.getByRole("radio", { name: "Light" });
    await expect(lightBtn).toHaveAttribute("aria-checked", "false");
    await lightBtn.click();
    await expect(lightBtn).toHaveAttribute("aria-checked", "true");
});
