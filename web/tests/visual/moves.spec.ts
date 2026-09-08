import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** The play-by-play: tapping what the coach named draws that move on the people,
 * in the ratified language. One golden per move that is built, so a change to
 * any of the drawings has to be looked at. */

const MOVES = [
  "toward",
  "away",
  "distance",
  "cutoff",
  "conflict",
  "fusion",
  "defined self",
  "inside",
  "outside",
  "overfunctioning",
  "underfunctioning",
  "projection",
  "anxiety up",
  "symptom up",
  "symptom down",
  "functioning down",
  "functioning up",
];

test.describe("the move language", () => {
  test.use({ storageState: stateFor("moves") });

  for (const move of MOVES) {
    test(`mid-move: ${move}`, async ({ page }) => {
      await page.goto("/companion/");
      await expect(page.locator(".bub.coach").first()).toBeVisible();
      await page.locator(".bub .chip", { hasText: move }).first().click();
      await expect(page.locator(".ss .cast")).toBeVisible();
      await page.waitForTimeout(700);
      await expect(page.locator(".pic")).toHaveScreenshot(
        `move-${move.replace(/ /g, "-")}.png`,
      );
    });
  }

  test("an offered chip goes into the message instead of aiming the picture", async ({
    page,
  }) => {
    await page.goto("/companion/");
    await expect(page.locator(".bub.coach").first()).toBeVisible();
    const offer = page.locator(".bub .chip.ask").first();
    await expect(offer).toHaveText("[winter 1993]");
    await offer.click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator(".inbar")).toHaveScreenshot("offer-in-composer.png");
  });

  test("what the coach named stays lit on the picture", async ({ page }) => {
    await page.goto("/companion/");
    await expect(page.locator(".ss")).toBeVisible();
    await page.waitForTimeout(500);
    await expect(page.locator(".ss-t.on").first()).toBeVisible();
    await expect(page.locator(".pic")).toHaveScreenshot("spotlight-at-rest.png");
  });
});

test.describe("the timeline behind the menu", () => {
  test.use({ storageState: stateFor("three40") });

  test("the list of everything, with the banner", async ({ page }) => {
    await page.goto("/companion/");
    await page.locator("#menu-open").click();
    await expect(page.locator("#menu-body .row").first()).toBeVisible();
    await expect(page.locator("#menu-screen")).toHaveScreenshot("menu-list.png");
  });
});
