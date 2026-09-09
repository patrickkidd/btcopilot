import { expect, test, type Page } from "@playwright/test";
import { stateFor, steady } from "./setup";

/** The moves board: the level a cluster opens into, and the chrome around the
 * drawings. The drawings themselves have their own goldens in moves.spec.ts;
 * these watch the things only the app can produce — the entry button, the
 * people the record puts on the ellipse, the pair bonds beneath them, the
 * earlier moves held behind the current one, the caption, and the step
 * controls at their ends.
 *
 * Driven the way a reader drives it: select a moment, take the entry button,
 * then step. No live coach turn is involved, so it is deterministic.
 *
 * The `moves` record is one moment per move the picture can draw, all in a
 * single cluster, so the board it opens has every move on it in order. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(400);
};

/** Select a moment so the caption row offers its cluster. */
const pickCluster = async (page: Page) => {
  // explain belongs to the cluster, not to a moment inside it, so nothing is
  // picked before it is taken (owner review round 3)
  const box = page.locator('.ss-hit[data-target="cluster"]');
  if (await box.first().isVisible().catch(() => false)) {
    await box.first().click();
    await page.waitForTimeout(400);
  }
  await expect(page.locator("#cap-play")).toBeEnabled();
};

const enter = async (page: Page) => {
  await pickCluster(page);
  await page.locator("#cap-play").click();
  // the way in opens the board itself now, with no coach turn behind it
  await expect(page.locator(".ss.board")).toBeVisible({ timeout: 30_000 });
  // past the .6s zoom, so the board is settled rather than mid-flight
  await page.waitForTimeout(800);
};

/** Hold every clock at one instant, or an 8, 10 or 12 second loop decides what
 * the shot catches. */
const freeze = (page: Page, ms = 2400) =>
  page.evaluate((at) => {
    for (const svg of document.querySelectorAll("svg")) {
      svg.pauseAnimations();
      svg.setCurrentTime(at / 1000);
    }
    for (const animation of document.getAnimations()) {
      animation.pause();
      animation.currentTime = at;
    }
  }, ms);

const picture = (page: Page) => page.locator(".pic");

test.describe("the moves board", () => {
  test.use({ storageState: stateFor("moves") });

  test("a cluster offers to walk its moves", async ({ page }) => {
    await settle(page);
    await pickCluster(page);
    await expect(page.locator("#cap-play")).toHaveText("explain");
    await expect(picture(page)).toHaveScreenshot("board-entry-offer.png", steady(page));
  });

  test("the board opens on the first move", async ({ page }) => {
    await settle(page);
    await enter(page);
    // the words under the board name the move, and never count them
    await expect(page.locator(".bcap")).toHaveText("Ada · toward");
    await freeze(page);
    await expect(picture(page)).toHaveScreenshot("board-first-move.png", steady(page));
  });

  test("earlier moves stay behind the one being drawn", async ({ page }) => {
    await settle(page);
    await enter(page);
    for (let i = 0; i < 4; i += 1)
      await page.locator('.pctl [data-target="next"]').click();
    await expect(page.locator(".bcap")).toHaveText("Ada · conflict");
    await freeze(page);
    await expect(picture(page)).toHaveScreenshot("board-fifth-move.png", steady(page));
  });

  test("the last move has nowhere further to go", async ({ page }) => {
    await settle(page);
    await enter(page);
    const next = page.locator('.pctl [data-target="next"]');
    while (await next.isEnabled()) await next.click();
    await expect(page.locator('.pctl [data-target="prev"]')).toBeEnabled();
    await freeze(page);
    await expect(picture(page)).toHaveScreenshot("board-last-move.png", steady(page));
  });

  // the one way up is the arrow beside the view's name; the board carries no
  // corner arrow of its own (owner ruling 2026-09-08)
  test("back goes up one level, to the cluster the board was showing", async ({
    page,
  }) => {
    await settle(page);
    const before = await picture(page).boundingBox();
    await enter(page);
    await expect(page.locator('[data-target="back"]')).toHaveCount(0);
    await page.locator("#up").click();
    await expect(page.locator(".ss.board")).toHaveCount(0);
    // past the .25s height transition, or the box is read mid-flight
    await page.waitForTimeout(500);
    const after = await picture(page).boundingBox();
    // the resting picture is one fixed height whatever it has been showing
    expect(after?.height).toBe(before?.height);
    await expect(picture(page)).toHaveScreenshot("board-back-to-wire.png", steady(page));
  });
});
