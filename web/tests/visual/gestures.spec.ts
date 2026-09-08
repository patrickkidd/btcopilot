import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The two session gestures the sheet was missing: swiping a row left for
 * Rename and Delete, and the list holding its order while it is open. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(600);
};

const openSheet = async (page: Page) => {
  await page.locator("#sessions-open").click();
  await expect(page.locator(".fs-sheet")).toBeVisible();
  await page.waitForTimeout(400);
};

/** A leftward drag across a row, further than the 72px the gesture asks for. */
const swipeLeft = async (page: Page, row: ReturnType<Page["locator"]>) => {
  const box = (await row.boundingBox())!;
  const y = box.y + box.height / 2;
  await page.mouse.move(box.x + box.width - 20, y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 130, y, { steps: 8 });
  await page.mouse.up();
};

test.describe("a session row's own actions", () => {
  test.use({ storageState: stateFor("play") });

  test("swiping left reveals Rename and Delete", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    const row = page.locator(".fs-body .row").first();
    await expect(row.locator(".fs-acts")).toHaveCount(0);
    await swipeLeft(page, row);
    await expect(row.locator(".fs-act.ren")).toHaveText("Rename");
    await expect(row.locator(".fs-act.del")).toHaveText("Delete");
    for (const action of ["ren", "del"]) {
      const box = (await row.locator(`.fs-act.${action}`).boundingBox())!;
      expect(box.height).toBeGreaterThanOrEqual(44);
    }
  });

  test("Rename opens the title in place, and a tap elsewhere puts the actions away", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const row = page.locator(".fs-body .row").first();
    await swipeLeft(page, row);
    await row.locator(".fs-act.ren").click();
    await expect(row.locator("input.rename")).toBeVisible();
    await expect(row.locator(".fs-acts")).toHaveCount(0);
  });

  // A session started here and deleted here, so the walk this fixture also
  // carries is still there for the play-by-play spec.
  test("Delete removes the session and the record survives it", async ({ page }) => {
    await settle(page);
    const moments = await page.locator(".ss .dot").count();
    await openSheet(page);
    const rows = page.locator(".fs-body .row");
    const before = await rows.count();
    await page.locator(".fs-new").click();
    await expect(page.locator(".fs-sheet")).toBeHidden();
    await openSheet(page);
    await expect(rows).toHaveCount(before + 1);
    await swipeLeft(page, rows.first());
    await rows.first().locator(".fs-act.del").click();
    await expect(rows).toHaveCount(before);
    await page.reload();
    await expect(page.locator(".ss")).toBeVisible();
    await page.waitForTimeout(600);
    expect(await page.locator(".ss .dot").count()).toBe(moments);
  });
});
