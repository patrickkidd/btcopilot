import { expect, test, type Page } from "./fixtures";
import { stateFor, type Key } from "./setup";

/** The pill strip on every shape of record, at phone and desktop sizes: one
 * pill per cluster with nothing drawn inside it, a dot only for an event no
 * cluster claims, the years as a ruler under the line, the line at most two
 * screens wide and opening at the present, and only pills and loose dots
 * answering a tap (R-0381, R-0543, R-0544). Deterministic gates, not pictures:
 * nothing outside the picture's height or the line's ends, no sideways scroll
 * of the page, no two years written over each other, every target a thumb's
 * height, no console error or failed request, and the picture changing after
 * every tap. */

const RECORDS: Key[] = ["empty", "one", "three40", "dense60", "hostile", "whitlock"];

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

type Box = { x: number; y: number; width: number; height: number };

/** Everything the strip draws or lays a target over, measured on the page. */
const measure = (page: Page) =>
  page.evaluate(() => {
    const box = (el: Element) => {
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    };
    const view = document.getElementById("view")!;
    const scroll = view.querySelector<HTMLElement>(".ss-scroll");
    return {
      view: box(view),
      line: box(view.querySelector(".ss-line") ?? view),
      pills: [...view.querySelectorAll("rect.pill")].map(box),
      dots: [...view.querySelectorAll("circle.dot")].map(box),
      years: [...view.querySelectorAll("text.ep-yrs")].map((t) => ({ ...box(t), text: t.textContent })),
      targets: [...view.querySelectorAll(".ss-hit")].map(box),
      sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      slides: scroll ? scroll.scrollWidth - scroll.clientWidth : 0,
      left: scroll?.scrollLeft ?? 0,
    };
  });

const within = (inner: Box, outer: Box) =>
  inner.x >= outer.x - 0.5 &&
  inner.y >= outer.y - 0.5 &&
  inner.x + inner.width <= outer.x + outer.width + 0.5 &&
  inner.y + inner.height <= outer.y + outer.height + 0.5;

/** Inside the picture's height, and across inside the line, which may be
 * wider than the picture and slide under it. */
const drawn = (inner: Box, at: { view: Box; line: Box }) =>
  within(inner, { x: at.line.x, y: at.view.y, width: at.line.width, height: at.view.height });

const overlap = (a: Box, b: Box) => a.x < b.x + b.width && b.x < a.x + a.width;

for (const key of RECORDS) {
  test.describe(`the strip on the ${key} record`, () => {
    test.use({ storageState: stateFor(key) });

    // R-0381, R-0543, R-0544
    test("draws inside the picture, at most two screens wide from the present, with its years apart", async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("requestfailed", (r) => errors.push(`failed: ${r.url()}`));
      await settle(page);
      const at = await measure(page);

      for (const mark of [...at.pills, ...at.dots, ...at.years, ...at.targets])
        expect(drawn(mark, at), JSON.stringify(mark)).toBe(true);
      expect(at.sideways).toBeLessThanOrEqual(0);
      expect(at.slides).toBeLessThanOrEqual(at.view.width);
      expect(at.left).toBe(at.slides);
      // nothing is drawn inside a pill
      for (const pill of at.pills)
        for (const dot of at.dots) expect(overlap(pill, dot), JSON.stringify(dot)).toBe(false);
      // no two years touch
      at.years.forEach((year, i) => {
        for (const other of at.years.slice(i + 1))
          expect(overlap(year, other), `${year.text} and ${other.text}`).toBe(false);
      });
      for (const target of at.targets) expect(target.height).toBeGreaterThanOrEqual(44);
      await expect(page.locator('#view .ss-hit[data-target="cluster"]')).toHaveCount(at.pills.length);
      await expect(page.locator('#view .ss-hit[data-target="zone"]')).toHaveCount(at.dots.length);
      expect(errors).toEqual([]);
    });

    // R-0381, R-0543, R-0544
    test("changes the picture after every tap on a pill or a dot", async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      await settle(page);
      const targets = page.locator("#view .ss-hit");
      const count = await targets.count();
      for (let i = 0; i < count; i += 1) {
        // back to the whole line before each tap
        await settle(page);
        const put = page.locator('#path [data-step="0"]');
        if (await put.count()) {
          await put.click();
          await page.waitForTimeout(400);
        }
        const before = await page.locator("#view").innerHTML();
        await page.locator("#view .ss-hit").nth(i).click();
        await page.waitForTimeout(400);
        expect(await page.locator("#view").innerHTML()).not.toBe(before);
        const at = await measure(page);
        for (const mark of [...at.pills, ...at.dots, ...at.targets])
          expect(drawn(mark, at), JSON.stringify(mark)).toBe(true);
        expect(at.sideways).toBeLessThanOrEqual(0);
      }
      expect(errors).toEqual([]);
    });
  });
}

test.describe("the strip in dark mode", () => {
  test.use({ storageState: stateFor("three40"), colorScheme: "dark" });

  // R-0543
  test("draws its pills and dots in the dark theme's data colour", async ({ page }) => {
    await settle(page);
    const colours = await page.evaluate(() => {
      const probe = document.createElement("span");
      probe.style.color = "var(--data)";
      document.body.append(probe);
      const data = getComputedStyle(probe).color;
      probe.remove();
      const fill = (sel: string) => getComputedStyle(document.querySelector(sel)!).fill;
      return { data, pill: fill("#view rect.pill"), dot: fill("#view circle.dot") };
    });
    expect(colours.pill).toBe(colours.data);
    expect(colours.dot).toBe(colours.data);
    // the dark theme's data colour, not the light one's
    expect(colours.data).not.toBe("rgb(14, 125, 120)");
  });
});
