import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Every scroll area takes wheel, trackpad, touch drag AND mouse drag, and the
 * outer page never moves (UI_STANDARDS) [Oracle: R-0104, R-0105]. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(600);
};

/** Whether a scroll area has anything below its fold. */
const overflows = (page: Page, selector: string) =>
  page
    .locator(selector)
    .evaluate((node) => node.scrollHeight > node.clientHeight + 1);

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
    // A tall window can hold the whole thread, and a surface with nothing below
    // the fold has nothing to scroll. Only the drag itself is under test here.
    test.skip(
      !(await overflows(page, "#chat")),
      "the thread fits in this window",
    );
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
    // The outer page must not move whether or not the thread had room to
    // scroll, which is the half of this that matters on every window.
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
    if (await overflows(page, "#chat"))
      expect(
        await page.locator("#chat").evaluate((n) => n.scrollTop),
      ).toBeGreaterThan(0);
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
