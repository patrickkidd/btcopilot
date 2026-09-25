import { expect, test, type Page } from "@playwright/test";
import { stateFor, type Key } from "./setup";

/** A thumb on a phone, on an open cluster: a tap on a dot picks that moment and
 * never the one beside it, and a tap on the picked moment's words opens its
 * editor rather than landing on the dot under them (owner, 2026-09-24). Real
 * touches at a phone's size, on records whose dots stand apart and whose dots
 * crowd each other closer than a thumb. */

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

async function openCluster(page: Page) {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  // the line comes to rest at the present; the first cluster is back at its start
  await page.evaluate(() => document.querySelector("#view .ss-scroll")?.scrollTo(0, 0));
  await page.waitForTimeout(400);
  const box = (await page.locator('#view .ss-hit[data-target="cluster"]').first().boundingBox())!;
  await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.locator('#view .ss-hit[data-target="zone"]').first()).toBeVisible();
  await page.waitForTimeout(400);
}

/** Tap the moment's dot, then the centre of its words and the centre of the
 * line of words nearest the dot, and see each reach its own control. */
async function tapBoth(page: Page, at: { x: number; y: number }, words: string) {
  await page.touchscreen.tap(at.x, at.y);
  await expect(page.locator("#view svg circle.dot.on")).toHaveCount(1);
  expect(Math.abs((await picked(page)) - at.x)).toBeLessThan(1);
  await expect(page.locator("#menu-screen")).toBeHidden();

  const lines = page.locator("#view .ss-t.on");
  const first = (await lines.first().boundingBox())!;
  const last = (await lines.last().boundingBox())!;
  for (const y of [(first.y + last.y + last.height) / 2, last.y + last.height / 2]) {
    await page.touchscreen.tap(first.x + first.width / 2, y);
    await expect(page.locator("#menu-screen")).toBeVisible();
    await expect(page.locator('#menu-body .editor .f[data-name="description"]')).toHaveValue(
      words,
    );
    await page.locator("#menu-close").click();
    await expect(page.locator("#menu-screen")).toBeHidden();
    await page.waitForTimeout(300);
  }
}

const cases: { key: Key; words: string[]; at: number[] }[] = [
  {
    key: "three40",
    words: ["Grandmother died", "The winter she stopped calling home", "The move across the country"],
    at: [0, 1, 2],
  },
  // twenty moments a month apart across the screen, about 18 points between dots
  {
    key: "dense60",
    words: Array.from({ length: 20 }, (_, i) => `Week ${i + 1}: sleep note`),
    at: [4, 5, 12],
  },
];

for (const { key, words, at } of cases) {
  test.describe(key, () => {
    test.use({ storageState: stateFor(key) });

    // R-0103
    test("a tap on a dot picks it and a tap on its words opens its editor", async ({ page }) => {
      await openCluster(page);
      const all = await centres(page);
      expect(all).toHaveLength(words.length);
      for (const i of at) await tapBoth(page, all[i], words[i]);
    });

    // R-0402
    test("a tap beside a dot, nearer it than its neighbour, picks that dot", async ({ page }) => {
      await openCluster(page);
      const all = await centres(page);
      for (const i of at) {
        const next = all[i + 1] ?? { x: all[i].x + 44 };
        const reach = Math.min(20, (next.x - all[i].x) / 2 - 2);
        await page.touchscreen.tap(all[i].x + reach, all[i].y);
        expect(Math.abs((await picked(page)) - all[i].x)).toBeLessThan(1);
      }
    });
  });
}

test.describe("dense60, every dot", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0103, R-0402
  test("a tap on each crowded dot's centre picks that dot, and every target is 44 tall", async ({
    page,
  }) => {
    await openCluster(page);
    const heights = await page
      .locator('#view .ss-hit[data-target="zone"]')
      .evaluateAll((all) => all.map((hit) => hit.getBoundingClientRect().height));
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
    const all = await centres(page);
    expect(all).toHaveLength(20);
    const missed: number[] = [];
    for (const [i, dot] of all.entries()) {
      await page.touchscreen.tap(dot.x, dot.y);
      if (Math.abs((await picked(page)) - dot.x) >= 1) missed.push(i);
    }
    expect(missed).toEqual([]);
  });
});
