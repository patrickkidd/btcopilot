import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Every word the app says can be selected and copied. Dragging a scroll area
 * and selecting a line of it are the same gesture, so where the press lands
 * decides: on the words it selects, in the space around them it scrolls. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(500);
};

/** Drag across one element's words, the way a reader does, and read back what
 * the browser thinks is selected. */
const dragAcross = async (page: Page, selector: string) => {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`nothing at ${selector}`);
  const y = box.y + 12;
  await page.mouse.move(box.x + 6, y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 6, y, { steps: 12 });
  await page.mouse.up();
  return page.evaluate(() => window.getSelection()?.toString() ?? "");
};

test.describe("what the app says can be taken away", () => {
  test.use({ storageState: stateFor("moves") });

  test("a coach bubble's words select", async ({ page }) => {
    await settle(page);
    expect((await dragAcross(page, ".bub.coach")).trim()).not.toBe("");
  });

  test("a session row's words select", async ({ page }) => {
    await settle(page);
    await page.locator("#sessions-open").click();
    await expect(page.locator(".fs-body .row").first()).toBeVisible();
    await page.waitForTimeout(400);
    expect((await dragAcross(page, ".fs-body .row .r1")).trim()).not.toBe("");
  });

  test("the words under the picture select", async ({ page }) => {
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator(".ss.board")).toBeVisible();
    await page.waitForTimeout(800);
    expect((await dragAcross(page, ".bcap")).trim()).not.toBe("");
  });

});

test.describe("dragging the thread", () => {
  // a record whose thread is long enough to have somewhere to scroll
  test.use({ storageState: stateFor("hostile") });

  test("still scrolls when the press lands off the words", async ({ page }) => {
    await settle(page);
    const chat = page.locator("#chat");
    const box = await chat.boundingBox();
    if (!box) throw new Error("no thread");
    await chat.evaluate((n) => (n.scrollTop = 0));
    const before = await chat.evaluate((n) => n.scrollTop);
    // down the left gutter, clear of every bubble's words
    await page.mouse.move(box.x + 3, box.y + box.height - 20);
    await page.mouse.down();
    await page.mouse.move(box.x + 3, box.y + 20, { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(600);
    expect(await chat.evaluate((n) => n.scrollTop)).toBeGreaterThan(before);
  });
});
