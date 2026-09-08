import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Step chips in a play-by-play (owner review round 1). The `play` record holds
 * one moment per move, all in one stored stretch, and its session holds a
 * play-by-play about that stretch whose chips are its moves in order.
 *
 * What is under test is routing, not drawing: a chip in a walk opens the board
 * if it is closed, goes to the move it names, and never puts the picture back
 * on the timeline. No coach turn is involved, so it is deterministic. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(400);
};

/** The chips of the walk, in the order the coach wrote them. */
const walk = (page: Page) => page.locator(".bub .chip.data");

const board = (page: Page) => page.locator(".ss.board");

test.describe("a chip in a play-by-play", () => {
  test.use({ storageState: stateFor("play") });

  test("the third chip opens the board on the third move", async ({ page }) => {
    await settle(page);
    await expect(board(page)).toHaveCount(0);
    await walk(page).nth(2).click();
    await expect(board(page)).toBeVisible();
    await expect(page.locator(".bcap")).toHaveText(/^3\//);
  });

  test("a further chip steps the board and never leaves it", async ({ page }) => {
    await settle(page);
    await walk(page).nth(2).click();
    await expect(page.locator(".bcap")).toHaveText(/^3\//);
    await walk(page).nth(6).click();
    await expect(board(page)).toBeVisible();
    await expect(page.locator(".bcap")).toHaveText(/^7\//);
  });

  test("the picture keeps its height while the walk is stepped", async ({
    page,
  }) => {
    await settle(page);
    await walk(page).nth(2).click();
    await expect(board(page)).toBeVisible();
    await page.waitForTimeout(800);
    const before = await page.locator(".pic").boundingBox();
    await walk(page).nth(6).click();
    await page.waitForTimeout(500);
    const after = await page.locator(".pic").boundingBox();
    expect(after?.height).toBe(before?.height);
  });
});
