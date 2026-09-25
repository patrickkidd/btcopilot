import { expect, test, type Page } from "@playwright/test";
import { KEYS, stateFor } from "./setup";

/** The picture holds what it draws. Nothing on it sits on top of anything else,
 * and nothing it writes leaves its frame — on every shape of record the app can
 * be handed, at rest and with a cluster open.
 *
 * The boxes are the ones drawn, not the targets around them: two targets may
 * touch where two clusters are close, and what must never touch is what the
 * reader can see. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

interface Box {
  what: string;
  x: number;
  y: number;
  right: number;
  bottom: number;
  /** The span it must stay inside: the scroller's scrollable content when it
   * rides in the line that scrolls sideways, the picture's frame otherwise. */
  edge: { x: number; right: number };
}

/** What the picture is showing, as boxes: the button that opens the list, the
 * cluster boxes, the words on the band, and the line the resting picture says
 * what to tap with. */
const boxes = (page: Page): Promise<Box[]> =>
  page.evaluate(() => {
    const seen: Box[] = [];
    const pic = document.querySelector("#chat-screen .pic")!.getBoundingClientRect();
    const span = (node: Element) => {
      const scroller = node.closest(".ss-scroll");
      if (!scroller) return { x: pic.x, right: pic.right };
      const x = scroller.getBoundingClientRect().x - scroller.scrollLeft;
      return { x, right: x + scroller.scrollWidth };
    };
    const take = (what: string, node: Element) => {
      const at = node.getBoundingClientRect();
      if (at.width < 1 || at.height < 1) return;
      seen.push({ what, x: at.x, y: at.y, right: at.right, bottom: at.bottom, edge: span(node) });
    };
    // a wide window draws no list button (R-0352)
    const list = document.getElementById("menu-open");
    if (list) take("the list button", list);
    for (const box of document.querySelectorAll(".ss .ep")) take("a cluster box", box);
    for (const words of document.querySelectorAll(".ss-t")) take("the words", words);
    // the year under the moment picked, and anything else written over the line
    // (the years inside a cluster box belong to that box and are not counted)
    for (const said of document.querySelectorAll(".ss-yr, .ss .brkl"))
      take("what the band says", said);
    const hint = document.querySelector(".ss-hint");
    if (hint) take("what to tap", hint);
    return seen;
  });

const overlaps = (a: Box, b: Box) =>
  a.x < b.right - 1 && b.x < a.right - 1 && a.y < b.bottom - 1 && b.y < a.bottom - 1;

/** Which pairs sit on top of one another, said in words. */
function collisions(all: Box[]): string[] {
  const out: string[] = [];
  for (let i = 0; i < all.length; i += 1)
    for (let j = i + 1; j < all.length; j += 1)
      if (overlaps(all[i], all[j]))
        out.push(`${all[i].what} over ${all[j].what}`);
  return out;
}

/** Whatever the picture has written, inside the frame it is written in. */
const escaped = async (page: Page) =>
  (await boxes(page))
    .filter((box) => box.x < box.edge.x - 1 || box.right > box.edge.right + 1)
    .map((box) => box.what);

for (const key of KEYS) {
  test.describe(`the picture on the ${key} record`, () => {
    test.use({ storageState: stateFor(key) });

    // R-0181, R-0134
    test("holds what it draws, at rest and with a cluster open", async ({ page }) => {
      await settle(page);
      expect(collisions(await boxes(page))).toEqual([]);
      expect(await escaped(page)).toEqual([]);

      const box = page.locator('.ss-hit[data-target="cluster"]').first();
      if (!(await box.isVisible().catch(() => false))) return;
      await box.click();
      await page.waitForTimeout(400);
      expect(collisions(await boxes(page))).toEqual([]);
      expect(await escaped(page)).toEqual([]);

      const dot = page.locator('.ss-hit[data-target="zone"]').first();
      if (!(await dot.isVisible().catch(() => false))) return;
      await dot.click();
      await page.waitForTimeout(300);
      expect(collisions(await boxes(page))).toEqual([]);
      expect(await escaped(page)).toEqual([]);
    });
  });
}
