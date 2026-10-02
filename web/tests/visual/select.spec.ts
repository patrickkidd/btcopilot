import { expect, test, type Page } from "@playwright/test";
import { stateFor, tellWithoutModel, boxOf } from "./setup";

/** Every word the app says can be selected and copied. Dragging a scroll area
 * and selecting a line of it are the same gesture, so where the press lands
 * decides: on the words it selects, in the space around them it scrolls. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

/** Drag across one element's words, the way a reader does, and read back what
 * the browser thinks is selected. */
const dragAcross = async (page: Page, selector: string) => {
  const box = await boxOf(page.locator(selector).first());
  const y = box.y + 12;
  await page.mouse.move(box.x + 6, y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 6, y, { steps: 12 });
  await page.mouse.up();
  return page.evaluate(() => window.getSelection()?.toString() ?? "");
};

test.describe("what the app says can be taken away", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0183
  test("a coach bubble's words select", async ({ page }) => {
    await settle(page);
    expect((await dragAcross(page, ".bub.coach")).trim()).not.toBe("");
  });

  // R-0183, R-0570
  test("the play-by-play's words select", async ({ page }) => {
    await tellWithoutModel(page);
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#pbp")).toBeVisible();
    await page.waitForTimeout(400);
    expect((await dragAcross(page, "#pbp .fact")).trim()).not.toBe("");
  });

});

test.describe("dragging the thread", () => {
  // a record whose thread is long enough to have somewhere to scroll
  test.use({ storageState: stateFor("hostile") });

  // R-0104
  test("still scrolls when the press lands off the words", async ({ page }) => {
    await settle(page);
    const chat = page.locator("#chat");
    const box = await boxOf(chat);
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

/** The wire's tap targets are tall so a thumb can find a dot, which is tall
 * enough to cover the second line of a label written above it. That line was
 * unreachable as words: a tap on it answered as the dot underneath, silently
 * naming a different moment (owner bug, 2026-09-08). The words of a loose
 * event lead to where it was said (R-0192). */
test.describe("a label that runs onto a second line", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0544
  test("answers on both of its lines, not just the first", async ({ page }) => {
    const rows = page.locator("#view .ss-t");
    /** Pick the first loose event afresh: one inside a cluster takes no pick
     * (R-0543), and each line is tried on a thread nothing has traced yet. */
    const pick = async () => {
      await settle(page);
      await page.locator('.ss-hit[data-target="zone"]').first().click();
      await page.waitForTimeout(400);
      await expect(rows).not.toHaveCount(0);
    };
    await pick();
    // the label wraps onto a second line on the phone's narrower picture; the
    // desktop window is wide enough to hold it on one. Every line it does take
    // has to answer, which is the bug this guards.
    const lines = await rows.count();
    if ((page.viewportSize()?.width ?? 0) < 500) expect(lines).toBe(2);

    // straight above the picked dot, and above the pill, where each mark's
    // own target reaches up under the words (R-0544)
    for (const mark of ["#view circle.dot.on", "#view rect.pill"])
      for (let row = 0; row < lines; row += 1) {
        await pick();
        const at = await boxOf(rows.nth(row));
        await expect(page.locator(".bub.traced")).toHaveCount(0);
        const under = await boxOf(page.locator(mark));
        const x = Math.min(Math.max(under.x + under.width / 2, at.x + 2), at.x + at.width - 2);
        await page.mouse.click(x, at.y + at.height / 2);
        // the words answered, going to where the event was said, not the mark
        // under them
        await expect(page.locator(".bub.traced")).toHaveCount(1);
        await expect(page.locator("#path")).not.toHaveText(/\u203a \d{4}/);
      }
  });
});
