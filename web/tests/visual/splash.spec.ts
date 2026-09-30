import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** Until the bundle has drawn the first screen the page shows only the splash,
 * never the app's own markup without its styles. */

const BUNDLE = "**/app/static/web/assets/**";

test.describe("the splash", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0091
  test("stands alone while the bundle has not arrived", async ({ page }) => {
    await page.route(BUNDLE, (route) => route.abort());
    await page.goto("/app/");
    await expect(page.locator("#splash")).toBeVisible();
    await expect(page.locator("#splash img")).toBeVisible();
    await expect(page.locator(".app")).toBeHidden();
    await expect(page.getByText("Your family")).toBeHidden();
    await expect(page.getByLabel("Message your coach")).toBeHidden();
  });

  // R-0091
  test("leaves the page once the app has drawn its first screen", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await expect(page.locator("#splash")).toHaveCount(0);
  });
});
