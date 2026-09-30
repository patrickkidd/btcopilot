import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** The icon a phone shows for the app added to its home screen: the Family
 * Diagram app's own icon, at every size the manifest and iOS ask for. */
test.use({ storageState: stateFor("one") });

/** A PNG's width and height, read from its header. */
const size = (png: Buffer) => `${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`;

// R-0055
test("the manifest icons and the apple-touch-icon are served at their sizes", async ({ page }) => {
  await page.goto("/app/");
  const touch = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  const where = await page.locator('link[rel="manifest"]').getAttribute("href");
  const manifest = await (await page.request.get(where!)).json();
  const wanted = [
    { src: touch!, sizes: "180x180" },
    ...(manifest.icons as { src: string; sizes: string }[]),
  ];
  expect(manifest.icons.map((i: { purpose: string }) => i.purpose)).toContain("maskable");
  for (const icon of wanted) {
    const response = await page.request.get(icon.src);
    expect(response.status(), icon.src).toBe(200);
    expect(response.headers()["content-type"], icon.src).toBe("image/png");
    expect(size(await response.body()), icon.src).toBe(icon.sizes);
  }
});
