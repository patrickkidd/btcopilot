import { expect, test } from "@playwright/test";
import { inside, stateFor, steady } from "./setup";

/** What the resting picture looks like on each shape of record, and what a tap
 * on it does. Goldens, so a change to the drawing has to be looked at.
 *
 * Held to the strict count rather than the suite's one percent: a percent of
 * this picture is hundreds of pixels, enough to hide a box becoming a bare dot,
 * which is exactly what it did hide once. */

const settle = async (page: import("@playwright/test").Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const picture = (page: import("@playwright/test").Page) => page.locator("#chat-screen .pic");

test.describe("the resting picture", () => {
  for (const [key, what] of [
    ["empty", "nothing has a date yet"],
    ["one", "one moment"],
    ["three40", "three moments over forty years"],
    ["dense60", "sixty moments in five years"],
  ] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      // R-0416
      test(`at rest: ${what}`, async ({ page }) => {
        await settle(page);
        await expect(picture(page)).toHaveScreenshot(`rest-${key}.png`, steady(page));
      });
    });
  }
});

/** The picture opens at rest showing the whole line, so a test about the wire
 * has to open a cluster first, which is what a reader does. */
const openCluster = async (page: import("@playwright/test").Page) => {
  await page.locator('.ss-hit[data-target="cluster"]').first().click();
  await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
  await page.waitForTimeout(400);
};

test.describe("a tap on a cluster", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0416
  test("opens it, and the wire underneath is tappable", async ({ page }) => {
    await settle(page);
    await expect(page.locator('.ss-hit[data-target="cluster"]').first()).toBeVisible();
    await openCluster(page);
    await expect(picture(page)).toHaveScreenshot("cluster-open.png", steady(page));
  });
});

test.describe("a tap on the wire", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0073
  test("picks the moment under it and writes it out", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
    await expect(page.locator("#view .ss-t.on").first()).not.toBeEmpty();
    await inside(page.locator("#view .ss-t.on").first(), picture(page));
  });

  // R-0072
  test("the chip beside it drops a reference in the composer", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await page.locator("#cap-chip").click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator("#composer .chip")).not.toBeEmpty();
    await inside(page.locator("#composer .chip"), page.locator("#chat-screen .inbar"));
  });
});

test.describe("the undated shelf", () => {
  test.use({ storageState: stateFor("empty") });

  // R-0359, R-0013
  test("is not drawn on the picture at all", async ({ page }) => {
    await settle(page);
    // Both question marks are off (R-0359): nothing told a first-time reader
    // what they meant. The shelf itself stays, reached from the events list,
    // so the picture offers no way to tap it and no mark to read.
    await expect(page.locator('#view .ss-hit[data-target="shelf"]')).toHaveCount(0);
    await expect(page.locator("#view .qm")).toHaveCount(0);
  });
});

/** The line is drawn a little wider than the screen and slides sideways under
 * it, so a crowded record reads at a scale a thumb can pick from (R-0381).
 * The dense record is the one wide enough to slide. */
test.describe("the resting line slides sideways", () => {
  test.use({ storageState: stateFor("dense60") });

  const line = (page: import("@playwright/test").Page) =>
    page.locator("#view .ss-scroll");

  const at = (page: import("@playwright/test").Page) =>
    line(page).evaluate((node) => ({
      left: node.scrollLeft,
      end: node.scrollWidth - node.clientWidth,
      screen: node.clientWidth,
    }));

  /** A swipe across the picture, which takes the line back into the earlier
   * years. */
  const swipe = async (page: import("@playwright/test").Page, by: number) => {
    await line(page).hover();
    await page.mouse.wheel(-by, 0);
    await page.waitForTimeout(600);
  };

  const yearsUnder = (page: import("@playwright/test").Page) =>
    page.locator("#view .ss-yrs span").allTextContents();

  // R-0381, R-0111
  test("opens with the most recent stretch filling the width", async ({ page }) => {
    await settle(page);
    const { left, end, screen } = await at(page);
    expect(end).toBeGreaterThan(0);
    expect(left).toBe(end);
    // one or two swipes, never a data project: two screens is the whole line
    expect(end + screen).toBeLessThanOrEqual(2 * screen);
  });

  // R-0381, R-0111
  test("a swipe takes it back to the earlier years", async ({ page }) => {
    await settle(page);
    const before = await yearsUnder(page);
    expect(before).toHaveLength(2);
    await swipe(page, 300);
    const now = await at(page);
    expect(now.left).toBeLessThan(now.end);
    const after = await yearsUnder(page);
    expect(Number(after[0])).toBeLessThan(Number(before[0]));
  });

  // R-0377
  test("every dot stays on the wire, wherever the line stands", async ({ page }) => {
    await settle(page);
    const onWire = async () =>
      page.locator("#view .ss svg").evaluate((svg) => {
        const wire = svg.querySelector("line.wire") as SVGLineElement;
        const y = Number(wire.getAttribute("y1"));
        return [...svg.querySelectorAll("circle")].every(
          (dot) => Number(dot.getAttribute("cy")) === y,
        );
      });
    expect(await onWire()).toBe(true);
    await swipe(page, 300);
    expect(await onWire()).toBe(true);
  });

  // no ruling
  test("settles where a cluster is not cut in half", async ({ page }) => {
    await settle(page);
    const settled = await line(page).evaluate((node) => ({
      type: getComputedStyle(node).scrollSnapType,
      stops: node.querySelectorAll(".ss-snap").length,
    }));
    expect(settled.type).toContain("x");
    expect(settled.stops).toBeGreaterThan(1);
  });

  // R-0045, R-0381
  test("a tap still picks the cluster under the thumb", async ({ page }) => {
    await settle(page);
    await swipe(page, 300);
    await page.locator('.ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
  });
});
