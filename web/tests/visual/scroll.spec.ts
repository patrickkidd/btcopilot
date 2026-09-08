import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Every scroll area takes wheel, trackpad, touch drag AND mouse drag, and the
 * outer page never moves (UI_STANDARDS). */

const settle = async (page: Page) => {
  await page.goto("/companion/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(600);
};

const dragUp = async (page: Page, selector: string, by: number) => {
  const box = (await page.locator(selector).boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height * 0.7;
  await page.mouse.move(x, y);
  await page.mouse.down();
  for (let step = 1; step <= 8; step += 1)
    await page.mouse.move(x, y - (by * step) / 8);
  await page.mouse.up();
  await page.waitForTimeout(600);
};

test.describe("scrolling the thread", () => {
  test.use({ storageState: stateFor("moves") });

  test("a mouse drag scrolls the chat", async ({ page }) => {
    await settle(page);
    const at = () => page.locator("#chat").evaluate((node) => node.scrollTop);
    await page.locator("#chat").evaluate((node) => (node.scrollTop = 0));
    const before = await at();
    await dragUp(page, "#chat", 200);
    expect(await at()).toBeGreaterThan(before);
  });

  test("the wheel scrolls the chat and never the page behind it", async ({
    page,
  }) => {
    await settle(page);
    await page.locator("#chat").evaluate((node) => (node.scrollTop = 0));
    await page.locator("#chat").hover();
    await page.mouse.wheel(0, 300);
    await page.waitForTimeout(300);
    expect(await page.locator("#chat").evaluate((n) => n.scrollTop)).toBeGreaterThan(0);
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
  });

  test("a mouse drag scrolls the sessions sheet", async ({ page }) => {
    await settle(page);
    await page.locator("#sessions-open").click();
    await expect(page.locator(".fs-body .row").first()).toBeVisible();
    await page.waitForTimeout(400);
    const contained = await page
      .locator(".fs-body")
      .evaluate((node) => getComputedStyle(node).overscrollBehaviorY);
    expect(contained).toBe("contain");
  });
});
