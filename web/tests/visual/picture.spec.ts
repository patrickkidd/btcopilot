import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** What the resting picture looks like on each shape of record, and what a tap
 * on it does. Goldens, so a change to the drawing has to be looked at. */

const settle = async (page: import("@playwright/test").Page) => {
  await page.goto("/companion/");
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
        await expect(picture(page)).toHaveScreenshot(`rest-${key}.png`);
      });
    });
  }
});

test.describe("a tap on the wire", () => {
  test.use({ storageState: stateFor("three40") });

  test("picks the moment under it and writes it out", async ({ page }) => {
    await settle(page);
    const zone = page.locator('.ss-hit[data-target="zone"]').first();
    await zone.click();
    await expect(page.locator(".ss-t.on").first()).toBeVisible();
    await expect(picture(page)).toHaveScreenshot("tap-moment.png");
  });

  test("the chip beside it drops a reference in the composer", async ({ page }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await page.locator("#cap-chip").click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator(".inbar")).toHaveScreenshot("chip-in-composer.png");
  });
});

test.describe("the undated shelf", () => {
  test.use({ storageState: stateFor("empty") });

  test("asks when, and nothing else", async ({ page }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="shelf"]').first().click();
    await expect(page.locator("#cap-chip")).toBeVisible();
    await expect(picture(page)).toHaveScreenshot("shelf-asked.png");
  });
});
