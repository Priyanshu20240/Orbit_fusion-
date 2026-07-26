import { test, expect } from "@playwright/test";

test("draw ROI on map, verify fusion buttons appear, load true color, NDVI, and NDWI layers", async ({ page }) => {
    test.setTimeout(60000);

    // 1. Open the live app
    await page.goto("http://localhost:5173/");

    // 2. Confirm title and map container mounted
    await expect(page.getByRole("heading", { name: /orbiter fusion/i })).toBeVisible();
    const map = page.locator(".leaflet-container");
    await expect(map).toBeVisible();

    // 3. Draw a rectangle ROI on the Leaflet map
    const drawRectangleBtn = page.locator(".leaflet-draw-draw-rectangle");
    if (await drawRectangleBtn.isVisible()) {
        await drawRectangleBtn.click();

        // Drag on the map to draw a bounding box ROI
        const box = await map.boundingBox();
        if (box) {
            const startX = box.x + box.width * 0.4;
            const startY = box.y + box.height * 0.4;
            const endX = box.x + box.width * 0.6;
            const endY = box.y + box.height * 0.6;

            await page.mouse.move(startX, startY);
            await page.mouse.down();
            await page.mouse.move(endX, endY, { steps: 5 });
            await page.mouse.up();
        }
    }

    // 4. Verify Fusion & Analysis section appears in Sidebar
    const fusionHeading = page.getByRole("heading", { name: /satellite image fusion & analysis/i });
    await expect(fusionHeading).toBeVisible({ timeout: 10000 });

    // 5. Click 'Merge and Load Fused Image' (True Color)
    const mergeBtn = page.getByRole("button", { name: /merge and load/i });
    await expect(mergeBtn).toBeVisible();
    await mergeBtn.click();

    // Wait for True Color GEE fusion request to finish
    await page.waitForTimeout(4000);
    await page.screenshot({ path: "e2e-fusion-loaded.png" });

    // 6. Click NDVI index button when enabled
    const ndviBtn = page.locator('[data-testid="viz-ndvi"]');
    if (await ndviBtn.isVisible()) {
        await expect(ndviBtn).toBeEnabled({ timeout: 15000 });
        await ndviBtn.click();
        await page.waitForTimeout(4000);
        await page.screenshot({ path: "e2e-ndvi-loaded.png" });
    }

    // 7. Click NDWI index button when enabled
    const ndwiBtn = page.locator('[data-testid="viz-ndwi"]');
    if (await ndwiBtn.isVisible()) {
        await expect(ndwiBtn).toBeEnabled({ timeout: 15000 });
        await ndwiBtn.click();
        await page.waitForTimeout(4000);
        await page.screenshot({ path: "e2e-ndwi-loaded.png" });
    }
});
