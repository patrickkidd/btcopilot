import { expect, test, type Page } from "@playwright/test";
import { stateFor, type Key } from "./setup";

/** A thumb on a phone, on the line: a tap on a loose event's dot picks that
 * event and never the one beside it, a tap on the picked event's words goes to
 * where it was said rather than landing on the dot under them (owner,
 * 2026-09-24), and a tap anywhere on a pill opens its cluster. An event inside a
 * cluster has no dot of its own (R-0543). Real touches at a phone's size, on a
 * record whose loose dots stand apart and on one whose pills fill the line. */

test.use({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } });

const dots = (page: Page) => page.locator("#view svg circle.dot");

/** Where each dot's centre is on the page, left to right. */
const centres = async (page: Page) =>
  (
    await dots(page).evaluateAll((all) =>
      all.map((dot) => {
        const r = dot.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
      }),
    )
  ).sort((a, b) => a.x - b.x);

const picked = async (page: Page) => {
  const r = (await page.locator("#view svg circle.dot.on").boundingBox())!;
  return r.x + r.width / 2;
};

async function rest(page: Page) {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
}

/** Tap the event's dot, then its words, and see each reach its own control. */
async function tapBoth(page: Page, at: { x: number; y: number }) {
  await page.touchscreen.tap(at.x, at.y);
  await expect(page.locator("#view svg circle.dot.on")).toHaveCount(1);
  expect(Math.abs((await picked(page)) - at.x)).toBeLessThan(1);

  const words = (await page.locator("#view .ss-t.on").first().boundingBox())!;
  await page.touchscreen.tap(words.x + words.width / 2, words.y + words.height / 2);
  await expect(page.locator(".bub.traced")).toHaveCount(1);
  await expect(page.locator("#menu-screen")).toBeHidden();
  await rest(page);
}

const cases: { key: Key; loose: number }[] = [
  { key: "three40", loose: 1 },
  // three long-named events after a cluster of three
  { key: "hostile", loose: 3 },
];

for (const { key, loose } of cases) {
  test.describe(key, () => {
    test.use({ storageState: stateFor(key) });

    // R-0103, R-0543
    test("a tap on a loose dot picks it and a tap on its words goes to where it was said", async ({
      page,
    }) => {
      await rest(page);
      const all = await centres(page);
      expect(all).toHaveLength(loose);
      for (const i of all.keys()) await tapBoth(page, (await centres(page))[i]);
    });

    // R-0402, R-0544
    test("a tap beside a dot, or above or below it, nearer it than its neighbour, picks that dot", async ({
      page,
    }) => {
      await rest(page);
      const all = await centres(page);
      for (const [i, dot] of all.entries()) {
        const next = all[i + 1] ?? { x: dot.x + 44 };
        const reach = Math.min(20, (next.x - dot.x) / 2 - 2);
        for (const [x, y] of [
          [dot.x + reach, dot.y],
          [dot.x, dot.y - 24],
          [dot.x, dot.y + 18],
        ]) {
          await page.touchscreen.tap(x, y);
          expect(Math.abs((await picked(page)) - dot.x)).toBeLessThan(1);
        }
      }
    });
  });
}

test.describe("dense60, every pill", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0103, R-0402, R-0544
  test("a tap on each pill opens its cluster, and every target is the strip's height", async ({
    page,
  }) => {
    await rest(page);
    const heights = await page
      .locator("#view .ss-hit")
      .evaluateAll((all) => all.map((hit) => hit.getBoundingClientRect().height));
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
    await expect(dots(page)).toHaveCount(0);
    const pills = await page.locator("#view rect.pill").evaluateAll((all) =>
      all.map((p) => {
        const r = p.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
      }),
    );
    expect(pills).toHaveLength(2);
    for (const pill of pills) {
      await page.touchscreen.tap(pill.x, pill.y);
      await expect(page.locator('#path [data-step="0"]')).toBeVisible();
      await expect(page.locator("#view rect.pill.on")).toHaveCount(1);
      // a second tap on the open pill puts it down
      await page.touchscreen.tap(pill.x, pill.y);
      await expect(page.locator("#path")).toHaveText("Timeline");
      await page.waitForTimeout(300);
    }
  });
});
