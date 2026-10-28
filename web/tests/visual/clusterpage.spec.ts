import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";

/** A cluster's page: the arrow keys step the current event through its list,
 * and every row carries its event's mark from the drawing above. */

test.use({ storageState: stateFor("hostile") });

const open = async (page: Page) => {
  await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
  await page.goto("/app/");
  await expect(page.locator(".bub").first()).toBeVisible();
  await page.waitForTimeout(1200);
  await page.locator('#view .ss-hit[data-target="cluster"]').first().click();
  await expect(page.locator("#info")).toBeVisible();
  await page.waitForTimeout(400);
  await page.locator("#info").click();
  await expect(page.locator("#view .ss.about")).toBeVisible();
  await page.waitForTimeout(800);
};

const rows = (page: Page) =>
  page.locator("#view .ab-list li[data-event]").evaluateAll((all) => all.map((li) => (li as HTMLElement).dataset.event!));

/** The events marked current on the list and on the drawing. */
const current = (page: Page) =>
  page.evaluate(() => ({
    rows: [...document.querySelectorAll<HTMLElement>("#view .ab-list li.on")].map((li) => li.dataset.event),
    dots: [...document.querySelectorAll<SVGElement>("#view .ab-draw circle.on")].map((c) => c.dataset.event),
  }));

/** Whether a keydown on the page is taken by it. */
const taken = (page: Page) =>
  page.evaluate(() => {
    const e = new KeyboardEvent("keydown", { key: "ArrowDown", cancelable: true });
    document.dispatchEvent(e);
    return e.defaultPrevented;
  });

// R-0954
test("the arrow keys step the current event through the cluster's list, stopping at the ends, its row scrolled into view", async ({ page }) => {
  await open(page);
  const ids = await rows(page);
  expect(ids.length).toBeGreaterThan(2);
  const dated = await page.locator("#view .ab-draw circle[data-event]").evaluateAll((all) => all.map((c) => (c as SVGElement).dataset.event!));
  const lit = (id: string) => ({ rows: [id], dots: dated.includes(id) ? [id] : [] });
  await page.keyboard.press("ArrowDown");
  expect(await current(page)).toEqual(lit(ids[0]));
  await page.keyboard.press("ArrowRight");
  expect(await current(page)).toEqual(lit(ids[1]));
  await page.keyboard.press("ArrowUp");
  expect(await current(page)).toEqual(lit(ids[0]));
  await page.keyboard.press("ArrowLeft");
  expect(await current(page)).toEqual(lit(ids[0]));
  // a tap on a row makes it current, and the keys move on from there
  await page.locator(`#view .ab-list li[data-event="${ids[1]}"]`).click();
  await page.keyboard.press("ArrowDown");
  expect(await current(page)).toEqual(lit(ids[2]));
  for (let n = 0; n < ids.length + 2; n++) await page.keyboard.press("ArrowDown");
  const last = ids[ids.length - 1];
  expect(await current(page)).toEqual(lit(last));
  await page.waitForTimeout(400);
  await expect(page.locator(`#view .ab-list li[data-event="${last}"]`)).toBeInViewport({ ratio: 1 });
  // typing in the message box keeps the keys for the text
  await page.locator("#composer").focus();
  await page.keyboard.press("ArrowUp");
  expect(await current(page)).toEqual(lit(last));
  await page.locator("#composer").blur();
  expect(await taken(page)).toBe(true);
  await page.locator("#view .card > .cardx").click();
  await expect(page.locator("#view .ss.about")).toHaveCount(0);
  expect(await taken(page)).toBe(false);
});

for (const scheme of ["light", "dark"] as const) {
  test.describe(scheme, () => {
    test.use({ colorScheme: scheme });

    // R-0955
    test(`each row carries its event's mark from the drawing, in one column left of the year (${scheme})`, async ({ page }) => {
      await open(page);
      const seen = await page.evaluate(() => {
        const paint = (c: Element | null | undefined) => {
          if (!c) return null;
          const s = getComputedStyle(c);
          return [s.stroke, s.fill, s.strokeWidth, c.getAttribute("r")].join(" ");
        };
        const line = (svg: Element, id: string) =>
          [...svg.querySelectorAll("line.ab-key")].find((l) => l.getAttribute("x1") === svg.querySelector(`circle[data-event="${id}"]`)?.getAttribute("cx"))
            ?.getAttribute("class") ?? null;
        const draw = document.querySelector("#view .ab-draw")!;
        return [...document.querySelectorAll<HTMLElement>("#view .ab-list li[data-event]")].map((li) => {
          const id = li.dataset.event!;
          const mark = li.firstElementChild!;
          const year = li.querySelector(".ab-yr")!.getBoundingClientRect();
          const box = mark.getBoundingClientRect();
          return {
            id,
            first: mark.getAttribute("class"),
            left: Math.round(box.left),
            before: box.right <= year.left,
            row: paint(mark.querySelector("circle")),
            dot: paint(draw.querySelector(`circle[data-event="${id}"]`)),
            rowLine: mark.querySelector("line")?.getAttribute("class") ?? null,
            dotLine: line(draw, id),
          };
        });
      });
      expect(seen.length).toBeGreaterThan(2);
      expect(new Set(seen.map((s) => s.left)).size).toBe(1);
      for (const s of seen) {
        expect(s.first).toBe("ab-mark");
        expect(s.before).toBe(true);
        expect(s.row).toBe(s.dot);
      }
      expect(seen.some((s) => s.row !== null)).toBe(true);
      // a key line through a dot is drawn through its row's mark too
      for (const s of seen.filter((s) => s.rowLine)) expect(s.dotLine).toBe(s.rowLine);
    });
  });
}
