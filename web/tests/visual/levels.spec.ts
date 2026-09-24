import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Going down a level and back up: the level arriving slides in from the right
 * over the one it came from, and going back slides it off the same way. */

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

// R-0224
test("opening a cluster slides it in from the right", async ({ page }) => {
  await settle(page);
  const [flight] = await fly(page, '.ss-hit[data-target="cluster"]');
  expect(flight.from).toBe("translateX(100%)");
  expect(flight.to).toBe("translateX(0px)");
});

// R-0224
test("going back slides the cluster off to the right, the same way reversed", async ({
  page,
}) => {
  await settle(page);
  const [into] = await fly(page, '.ss-hit[data-target="cluster"]');
  await page.waitForTimeout(600);
  const [back] = await fly(page, "#up");
  expect(back.from).toBe(into.to);
  expect(back.to).toBe(into.from);
  expect(back.ms).toBe(into.ms);
});

// R-0224
test("the arriving level covers the one it came from", async ({ page }) => {
  await settle(page);
  const [flight] = await fly(page, '.ss-hit[data-target="cluster"]');
  expect(flight.covers).toBe(true);
  expect(flight.ground).not.toMatch(/rgba\(0, 0, 0, 0\)|transparent/);
});
