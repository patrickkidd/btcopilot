import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Only something entirely new slides: the about page and the board arrive
 * from the right over the line and go back off it the same way. Picking a
 * cluster or a moment on the line, and putting it down, moves nothing: only
 * the emphasis and the path change in place (R-0542). */

test.use({ storageState: stateFor("three40") });

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

interface Flight {
  from: string;
  to: string;
  ms: number;
  covers: boolean;
  ground: string;
}

/** Tap something and read the card that travels, the frame after it starts. */
const fly = (page: Page, selector: string) =>
  page.evaluate(
    (sel) =>
      new Promise<Flight[]>((done) => {
        (document.querySelector(sel) as HTMLElement).click();
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            const region = document.querySelector(".pic")!.getBoundingClientRect();
            done(
              [...document.querySelectorAll(".pic .slide-lay")].flatMap((lay) =>
                lay.getAnimations().map((a) => {
                  const frames = (a.effect as KeyframeEffect).getKeyframes();
                  const box = lay.getBoundingClientRect();
                  return {
                    from: String(frames[0].transform),
                    to: String(frames.at(-1)!.transform),
                    ms: Number(a.effect!.getTiming().duration),
                    covers:
                      Math.abs(box.top - region.top) < 1 &&
                      Math.abs(box.height - region.height) < 1 &&
                      Math.abs(box.width - region.width) < 1,
                    ground: getComputedStyle(lay).backgroundColor,
                  };
                }),
              ),
            );
          }),
        );
      }),
    selector,
  );

const open = async (page: Page) => {
  await page.locator('.ss-hit[data-target="cluster"]').first().click();
  await expect(page.locator('#path [data-step="0"]')).toBeVisible();
};

// R-0542, R-0543
test("picking a cluster or a moment, and putting it down, slides nothing", async ({
  page,
}) => {
  await settle(page);
  expect(await fly(page, '.ss-hit[data-target="cluster"]')).toEqual([]);
  await page.waitForTimeout(300);
  expect(await fly(page, '#path [data-step="0"]')).toEqual([]);
  await page.waitForTimeout(300);
  // only an event no cluster claims is picked on the line
  expect(await fly(page, '.ss-hit[data-target="zone"]')).toEqual([]);
  await page.waitForTimeout(300);
  expect(await fly(page, '#path [data-step="0"]')).toEqual([]);
});

// R-0224, R-0542
test("the about page slides in from the right", async ({ page }) => {
  await settle(page);
  await open(page);
  const [flight] = await fly(page, "#info");
  expect(flight.from).toBe("translateX(100%)");
  expect(flight.to).toBe("translateX(0px)");
});

// R-0224, R-0542
test("going back slides the about page off to the right, the same way reversed", async ({
  page,
}) => {
  await settle(page);
  await open(page);
  const [into] = await fly(page, "#info");
  await page.waitForTimeout(600);
  const [back] = await fly(page, '#path [data-step="1"]');
  expect(back.from).toBe(into.to);
  expect(back.to).toBe(into.from);
  expect(back.ms).toBe(into.ms);
});

// R-0224
test("the arriving level covers the one it came from", async ({ page }) => {
  await settle(page);
  await open(page);
  const [flight] = await fly(page, "#info");
  expect(flight.covers).toBe(true);
  expect(flight.ground).not.toMatch(/rgba\(0, 0, 0, 0\)|transparent/);
});

/** Tap something and read where the line stands on every frame for a while. */
const travel = (page: Page, selector: string, nth = 0) =>
  page.evaluate(
    ([sel, n]) =>
      new Promise<number[]>((done) => {
        const at = () => document.querySelector(".ss-scroll")!.scrollLeft;
        const seen = [at()];
        (document.querySelectorAll(sel)[n] as HTMLElement).click();
        const end = performance.now() + 700;
        const frame = () => {
          seen.push(at());
          if (performance.now() < end) requestAnimationFrame(frame);
          else done([...new Set(seen)]);
        };
        requestAnimationFrame(frame);
      }),
    [selector, nth] as const,
  );

/** Whitlock's line is wider than the screen and opens at the present
 * (R-0381); opening a cluster, explaining it and going back through the
 * drawer's path must never move it (R-0542). */
test.describe("on the record with the longest line", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0542, R-0381
  test("opening a cluster, explaining it and going back leave the line where it stands", async ({
    page,
  }) => {
    await settle(page);
    const statements = await page.evaluate(async () => {
      const sessions = await (await fetch("/app/sessions")).json();
      return (await (await fetch(`/app/sessions/${sessions[0].id}`)).json()).statements;
    });
    const play = statements.find((s: { case: unknown }) => s.case);
    await page.route(/\/app\/play(\?diagram_id=\d+)?$/, (route) =>
      route.fulfill({
        json: { statement: play.text, statement_id: play.id, kind: "play", cluster_id: play.cluster_id, case: play.case },
      }),
    );
    const line = await page.locator(".ss-scroll").evaluate((s) => ({
      left: s.scrollLeft,
      end: s.scrollWidth - s.clientWidth,
      screens: s.scrollWidth / s.clientWidth,
    }));
    expect(line.end).toBeGreaterThan(0);
    expect(line.screens).toBeLessThanOrEqual(2);
    expect(line.left).toBe(line.end);
    expect(await travel(page, '.ss-hit[data-target="cluster"]')).toEqual([line.end]);
    expect(await travel(page, "#cap-play")).toEqual([line.end]);
    await expect(page.locator("#pbp")).toBeVisible();
    expect(await travel(page, '#pbp .path [data-step="1"]')).toEqual([line.end]);
    await expect(page.locator("#pbp")).toBeHidden();
  });
});

test.describe("on a wide line with many clusters", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0542
  test("opening one cluster after another leaves the line where it stands", async ({ page }) => {
    await settle(page);
    const cluster = '.ss-hit[data-target="cluster"]';
    // the later cluster is on screen at the present; the earlier one is
    // reached by sliding the line to its start first, as a thumb would
    expect(await travel(page, cluster, 1)).toHaveLength(1);
    await page.locator('#path [data-step="0"]').click();
    await page.locator(".ss-scroll").evaluate((s) => (s.scrollLeft = 0));
    expect(await travel(page, cluster, 0)).toHaveLength(1);
  });
});
