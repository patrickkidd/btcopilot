import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The taps below pin two rulings: a first tap looks and costs nothing [Oracle: R-0073],
 * and tapping a piece of data opens where in the record it came up [Oracle: R-0140]. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
};

test.describe("a tap on a message's own words", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0073, R-0168, R-0543
  test("lights what that message named, and costs no turn", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(600);
    const bubble = page.locator(".bub.coach").last();
    const before = (await page.locator("#chat-screen .pic").boundingBox())!;
    await bubble.click({ position: { x: 6, y: 6 } });
    await page.waitForTimeout(300);
    // what the message named is lit on the picture; with a cluster open the
    // drawing carries no words at all (owner, 2026-09-09), only the lit pill
    // that holds what was named
    expect(await page.locator("#view .dot.lit, #view rect.pill.on").count()).toBeGreaterThan(0);
    // nothing entered the composer, and nothing above the chat moved
    expect(await page.locator("#composer").innerText()).toBe("");
    const after = (await page.locator("#chat-screen .pic").boundingBox())!;
    expect(after.height).toBe(before.height);
  });

  // R-0134
  test("never writes more than three rows of words", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(600);
    await page.locator(".bub.coach").last().click({ position: { x: 6, y: 6 } });
    await page.waitForTimeout(300);
    expect(await page.locator("#view .ss-t").count()).toBeLessThanOrEqual(3);
  });
});
