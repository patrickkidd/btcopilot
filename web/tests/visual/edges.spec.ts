import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** In every picture view below the whole line, the first step of the path at
 * the top left starts where the line starts and where the row under the line
 * starts: one left edge down the picture, the page's 16 in from its side. Its
 * tap target stays 44 tall around the word [Oracle: R-0234, R-0540].
 *
 * The word's edge is its ink, measured with the font it is drawn in, not the
 * box around it, because the box carries the glyph's own side bearing. */

const GUTTER = 16;

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
};

/** Past the slide one level takes into another. */
const tap = async (page: Page, what: string) => {
  await page.locator(what).first().click();
  await page.waitForTimeout(700);
};

const edges = (page: Page) =>
  page.evaluate(() => {
    const button = document.querySelector<HTMLElement>("#path > :first-child")!;
    const range = document.createRange();
    range.selectNodeContents(button);
    const box = range.getBoundingClientRect();
    const pen = document.createElement("canvas").getContext("2d")!;
    pen.font = getComputedStyle(button).font;
    const ink = pen.measureText(button.textContent!.trim());
    const target = getComputedStyle(button, "::before");
    const left = (sel: string) => {
      const el = document.querySelector(sel);
      return el ? el.getBoundingClientRect().left : null;
    };
    return {
      picture: document.querySelector(".pic")!.getBoundingClientRect().left,
      glyph: box.left - ink.actualBoundingBoxLeft,
      line: left("#view line.wire"),
      ask: left("#caption > :first-child"),
      target: [parseFloat(target.width), parseFloat(target.height)],
    };
  });

/** One left edge: the glyph, the line and the ask button where the view has
 * them, all the gutter in from the picture's side. */
const lined = async (page: Page, view: string, has: { line: boolean; ask: boolean }) => {
  const at = await edges(page);
  expect(Math.abs(at.glyph - at.picture - GUTTER), `${view}: the glyph`).toBeLessThanOrEqual(1);
  if (has.line) expect(Math.abs(at.line! - at.glyph), `${view}: the line`).toBeLessThanOrEqual(1);
  if (has.ask) expect(Math.abs(at.ask! - at.glyph), `${view}: ask`).toBeLessThanOrEqual(1);
  expect(Math.min(...at.target), `${view}: the tap target`).toBeGreaterThanOrEqual(44);
};

test.describe("the timeline's views", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0234, R-0540
  test("the path over an event picked on the whole line", async ({ page }) => {
    await settle(page);
    await tap(page, `#view .ss-hit[data-target="zone"][aria-label="Stopped calling"]`);
    await lined(page, "picked at rest", { line: true, ask: true });
  });

  // R-0234, R-0540, R-0543
  test("the path over an open cluster and its about page", async ({ page }, info) => {
    await settle(page);
    await tap(page, `#view .ss-hit[data-target="cluster"]`);
    await lined(page, "open cluster", { line: true, ask: true });
    await page.screenshot({ path: info.outputPath(`edges-${info.project.name}.png`) });

    await tap(page, "#info");
    await lined(page, "about", { line: false, ask: false });
  });
});

