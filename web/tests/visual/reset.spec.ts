import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

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
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
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
  await expect(page.locator(".ss-t.on").first()).toBeVisible();
};

test.describe("putting the picture down", () => {
  test.use({ storageState: stateFor("three40") });

  test("a tap on empty wire shows the whole line again", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);

    // the far right of the picture, clear of every moment and every label
    const box = (await page.locator(".ss").boundingBox())!;
    await page.mouse.click(box.x + box.width - 4, box.y + box.height - 4);

    await expect(page.locator(".ss-t.on")).toHaveCount(0);
    await expect(resting(page).first()).toBeVisible();
  });

  test("the name of the picture does the same", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);

    await page.locator("#crumb").click();
    await expect(page.locator(".ss-t.on")).toHaveCount(0);
    await expect(resting(page).first()).toBeVisible();
  });
});

/** The labels sit under the band's tap target, so a tap on one is a press at
 * its own place on the picture. */
const tapWords = async (page: Page, index = 0) => {
  const label = page.locator(".ss-t.on").nth(index);
  const box = (await label.boundingBox())!;
  await page.mouse.click(box.x + Math.min(40, box.width / 2), box.y + box.height / 2);
};

test.describe("a tap on a label", () => {
  test.use({ storageState: stateFor("moves") });

  test("picks its moment, and opens its editor when tapped again", async ({
    page,
  }) => {
    await settle(page);
    // the coach's last message names moments, so the wire carries their labels
    await expect(page.locator(".ss-t.on").first()).toBeVisible();

    await tapWords(page);
    // one moment is picked: its words are on the band and its year under its dot
    await expect(page.locator(".ss-yr.on")).toHaveCount(1);

    // again, on a picture showing one cluster: the moment's own editor
    await tapWords(page);
    await expect(page.locator("#menu-screen")).toBeVisible();
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(page.locator("#menu-body .editor")).toBeVisible();
  });

  test("a dot picks its moment and never travels", async ({ page }) => {
    await settle(page);
    // whether the picture opens on the whole line or on one cluster depends on
    // what the coach last named, so the cluster is opened when there is one
    const box = page.locator('.ss-hit[data-target="cluster"]');
    if (await box.first().isVisible().catch(() => false)) {
      await box.first().click();
      await page.waitForTimeout(400);
    }
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".ss-yr.on")).toHaveCount(1);
    // the same dot again: still picked, and the thread has not moved
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".ss-yr.on")).toHaveCount(1);
    await expect(page.locator(".bub.traced")).toHaveCount(0);
  });
});
