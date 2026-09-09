import { expect, test } from "@playwright/test";
import { stateFor, steady } from "./setup";

/** What the resting picture looks like on each shape of record, and what a tap
 * on it does. Goldens, so a change to the drawing has to be looked at.
 *
 * Held to the strict count rather than the suite's one percent: a percent of
 * this picture is hundreds of pixels, enough to hide a box becoming a bare dot,
 * which is exactly what it did hide once. */

const settle = async (page: import("@playwright/test").Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const picture = (page: import("@playwright/test").Page) => page.locator(".pic");

test.describe("the resting picture", () => {
  for (const [key, what] of [
    ["empty", "nothing has a date yet"],
    ["one", "one moment"],
    ["three40", "three moments over forty years"],
    ["dense60", "sixty moments in five years"],
  ] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      test(`at rest: ${what}`, async ({ page }) => {
        await settle(page);
        await expect(picture(page)).toHaveScreenshot(`rest-${key}.png`, steady(page));
      });
    });
  }
});

/** The picture opens at rest showing the whole line, so a test about the wire
 * has to open a cluster first, which is what a reader does. */
const openCluster = async (page: import("@playwright/test").Page) => {
  await page.locator('.ss-hit[data-target="cluster"]').first().click();
  await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
  await page.waitForTimeout(400);
};

test.describe("a tap on a cluster", () => {
  test.use({ storageState: stateFor("three40") });

  test("opens it, and the wire underneath is tappable", async ({ page }) => {
    await settle(page);
    await expect(page.locator('.ss-hit[data-target="cluster"]').first()).toBeVisible();
    await openCluster(page);
    await expect(picture(page)).toHaveScreenshot("cluster-open.png", steady(page));
  });
});

test.describe("a tap on the wire", () => {
  test.use({ storageState: stateFor("three40") });

  test("picks the moment under it and writes it out", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".ss-t.on").first()).toBeVisible();
    await expect(picture(page)).toHaveScreenshot("tap-moment.png", steady(page));
  });

  test("the chip beside it drops a reference in the composer", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await page.locator("#cap-chip").click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator(".inbar")).toHaveScreenshot("chip-in-composer.png", steady(page));
  });
});

test.describe("the undated shelf", () => {
  test.use({ storageState: stateFor("empty") });

  test("asks when, and nothing else", async ({ page }) => {
    await settle(page);
    // an empty record has no cluster to open, so the shelf is reachable at rest
    await page.locator('.ss-hit[data-target="shelf"]').first().click();
    await expect(page.locator("#cap-chip")).toBeVisible();
    await expect(picture(page)).toHaveScreenshot("shelf-asked.png", steady(page));
  });
});
