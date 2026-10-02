import { expect, test, type Page } from "@playwright/test";
import { stateFor, boxOf } from "./setup";

/** Putting the picture down, and what a label does.
 *
 * Anything on the picture that is not a moment, a label or a control is
 * ground: a tap there clears what is picked and shows the whole line again.
 * The name of the picture does the same.
 *
 * A label picks the moment it names; tapping the words of the moment already
 * picked goes to where it was said in the conversation. Only the words travel:
 * a dot picks and never moves the thread. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

/** The resting picture: clusters to open, and nothing written on the wire. */
const resting = (page: Page) => page.locator('.ss-hit[data-target="cluster"]');

const openCluster = async (page: Page) => {
  await resting(page).first().click();
  await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
  await page.waitForTimeout(400);
};

const pickMoment = async (page: Page) => {
  await page.locator('.ss-hit[data-target="zone"]').first().click();
  await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
};

test.describe("putting the picture down", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0462
  test("a tap on empty wire shows the whole line again", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);

    // the foot of the picture, under every moment's target and every label
    const box = await boxOf(page.locator("#view .ss"));
    await page.mouse.click(box.x + box.width - 4, box.y + box.height - 1);

    await expect(page.locator("#view .ss-t.on")).toHaveCount(0);
    await expect(resting(page).first()).toBeVisible();
  });

  // R-0362, R-0223, R-0540
  test("the whole timeline in the path closes the cluster, picked moment or not", async ({
    page,
  }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);

    // The first step of the path closes the cluster outright: putting the
    // moment down first was tap-for-tap logical and felt wrong (R-0362). The
    // cluster's own step puts the moment down and keeps the cluster open.
    await page.locator('#path [data-step="0"]').click();
    await expect(page.locator("#view circle.dot.on")).toHaveCount(0);
    await expect(page.locator("#view .ss-t.on")).toHaveCount(0);
    await expect(resting(page).first()).toBeVisible();
    await expect(page.locator("#path")).toHaveText("Timeline");
  });
});

test.describe("a tap on the words of the moment picked", () => {
  // a loose event, the only kind a tap picks (R-0543)
  test.use({ storageState: stateFor("three40") });

  /** Pick a moment, so the band carries its words rather than the cluster's. */
  const pickOne = async (page: Page) => {
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#view circle.dot.on")).toHaveCount(1);
  };

  // R-0460, R-0543
  test("a dot picks its moment and never travels", async ({ page }) => {
    await settle(page);
    await pickOne(page);
    // the same dot again: still picked, and the thread has not moved
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#view circle.dot.on")).toHaveCount(1);
    await expect(page.locator(".bub.traced")).toHaveCount(0);
  });
});
