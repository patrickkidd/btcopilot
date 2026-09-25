import { expect, test, type Page } from "@playwright/test";
import { flask, stateFor, username } from "./setup";

/** A chip naming an event and the event's own dot pick it the same way
 * [Oracle: R-0168]: the others fade, an event outside every cluster keeps the
 * clusters as brackets under the line [Oracle: R-0235], and the picture keeps
 * its height [Oracle: R-0377, R-0460]. The old chip spotlight comes back for
 * one person when an admin sets it, and goes again when set back.
 *
 * The hostile record: one cluster holds parts 1 to 3, parts 4 to 6 are loose,
 * and the coach's reply names each part in a chip. */

const WHO = username("hostile");

/** The admin command, run the way Patrick runs it. */
const spotlight = (value: string) =>
  flask("admin", "run", "--", "users", "prefs", WHO, "spotlight", value, "--yes");

const open = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
};

/** Past the slide one level takes into another. */
const tapped = async (page: Page, what: string) => {
  await page.locator(what).first().tap();
  await page.waitForTimeout(700);
};

const chip = (part: number) => `#chat .bub .chip:text-is("moment number ${part}")`;
const dot = (part: number) =>
  `#view .ss-hit[data-target="zone"][aria-label$="part ${part}"]`;
const CLUSTER = `#view .ss-hit[data-target="cluster"]`;

/** What the picture shows, and where the line, the picture and the chat stand. */
const shown = (page: Page) =>
  page.evaluate(() => {
    const view = document.getElementById("view")!;
    const others = [...view.querySelectorAll("circle.dot:not(.on)")];
    return {
      brackets: view.querySelectorAll("rect.ep").length,
      picked: view.querySelectorAll("circle.dot.on").length,
      faded: others.length > 0 && others.every((d) => Number(d.getAttribute("opacity")) < 1),
      words: [...view.querySelectorAll(".ss-t.on")].map((t) => t.textContent).join(" "),
      line: Math.round(view.querySelector("line.wire")!.getBoundingClientRect().top),
      height: Math.round(view.getBoundingClientRect().height),
    };
  });
/** Where the chip sits on screen, so the chat under the picture is seen not to move. */
const chipTop = async (page: Page, part: number) =>
  Math.round((await page.locator(chip(part)).first().boundingBox())!.y);

test.use({ storageState: stateFor("hostile"), hasTouch: true });

test.beforeAll(() => spotlight("unified"));
test.afterAll(() => spotlight("unified"));

// R-0168, R-0235, R-0377, R-0460
test("a chip and a dot pick a loose event the same way", async ({ page }, info) => {
  await open(page);
  const height = (await shown(page)).height;
  await page.locator(chip(4)).first().scrollIntoViewIfNeeded();
  const top = await chipTop(page, 4);
  await tapped(page, chip(4));
  const byChip = await shown(page);
  expect(byChip.picked).toBe(1);
  expect(byChip.brackets).toBeGreaterThan(0);
  expect(byChip.faded).toBe(true);
  expect(byChip.height).toBe(height);
  expect(await chipTop(page, 4)).toBe(top);
  await page.screenshot({ path: info.outputPath(`chip-${info.project.name}.png`) });

  await open(page);
  await tapped(page, dot(4));
  expect(await shown(page)).toEqual(byChip);
});

// R-0168, R-0377
test("a chip and a dot pick an event inside a cluster the same way", async ({ page }) => {
  await open(page);
  await tapped(page, chip(2));
  const byChip = await shown(page);
  expect(byChip.picked).toBe(1);
  expect(byChip.faded).toBe(true);

  await open(page);
  await tapped(page, CLUSTER);
  await tapped(page, dot(2));
  expect(await shown(page)).toEqual(byChip);
});

// R-0168
test("the old chip spotlight comes back when an admin sets it", async ({ page }) => {
  spotlight("chip");
  await open(page);
  await tapped(page, chip(4));
  const byChip = await shown(page);
  expect(byChip.picked).toBe(1);
  expect(byChip.brackets).toBe(0);

  await open(page);
  await tapped(page, dot(4));
  expect((await shown(page)).brackets).toBeGreaterThan(0);

  spotlight("unified");
  await open(page);
  await tapped(page, chip(4));
  expect((await shown(page)).brackets).toBeGreaterThan(0);
});
