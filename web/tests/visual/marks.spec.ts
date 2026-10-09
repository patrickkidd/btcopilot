import { expect, test } from "./fixtures";
import { stateFor, tellWithoutModel } from "./setup";

/** The up and down marks beside a person in the play-by-play. They used to fade out
 * for half of the loop, so a reader who looked away found nothing there. The
 * mark is on screen for the whole loop now, and says which way it went by
 * travelling along its own axis instead. */

const LOOP = [0, 1000, 2400, 4000, 5200, 6800, 7900];

test.use({ storageState: stateFor("moves") });

// R-0163, R-0570
test("the symptom mark is on screen for the whole loop", async ({ page }) => {
  test.skip(test.info().project.name !== "phone");
  // a play-by-play that opens on the record's symptom rising
  await tellWithoutModel(page, (e) => !!(e.symptom || e.functioning));
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
  await page.locator("#cap-play").click();
  await expect(page.locator("#pbp .draw .sym-arrow.worse")).toHaveCount(1);

  const seen = [];
  for (const at of LOOP)
    seen.push(
      await page.evaluate((ms) => {
        for (const svg of document.querySelectorAll("svg")) {
          svg.pauseAnimations();
          svg.setCurrentTime(ms / 1000);
        }
        for (const animation of document.getAnimations()) {
          animation.pause();
          animation.currentTime = ms;
        }
        const mark = document.querySelector(".sym-arrow");
        if (!mark) return null;
        const style = getComputedStyle(mark);
        return { opacity: style.opacity, y: new DOMMatrix(style.transform).f };
      }, at),
    );

  expect(seen.map((s) => s?.opacity)).toEqual(LOOP.map(() => "1"));
  // and it moves: the travel is what says which way it went
  expect(new Set(seen.map((s) => s?.y)).size).toBeGreaterThan(1);
});
