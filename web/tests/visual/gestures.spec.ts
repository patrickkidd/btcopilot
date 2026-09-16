import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The two session gestures the sheet was missing: swiping a row left for
 * Rename and Delete, and the list holding its order while it is open. The taps
 * below pin two rulings: a first tap looks and costs nothing [Oracle: R-0073],
 * and tapping a datum shows where it was mentioned [Oracle: R-0140]. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
};

const openSheet = async (page: Page) => {
  await page.locator("#sessions-open").click();
  await expect(page.locator("#sessions-sheet")).toBeVisible();
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
    const row = page.locator("#sessions-sheet .fs-body .row").first();
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
    const row = page.locator("#sessions-sheet .fs-body .row").first();
    await swipeLeft(page, row);
    await row.locator(".fs-act.ren").click();
    await expect(row.locator("input.rename")).toBeVisible();
    await expect(row.locator(".fs-acts")).toHaveCount(0);
  });

  // A session started here and deleted here, so the walk this fixture also
  // carries is still there for the play-by-play spec.
  test("Delete removes the session and the record survives it", async ({ page }) => {
    await settle(page);
    const moments = await page.locator("#view .ss .dot").count();
    await openSheet(page);
    const rows = page.locator("#sessions-sheet .fs-body .row");
    const before = await rows.count();
    // the foot also carries the upload and note buttons of the same class
    await page.locator("#sessions-sheet .fs-new").first().click();
    await expect(page.locator("#sessions-sheet")).toBeHidden();
    await openSheet(page);
    await expect(rows).toHaveCount(before + 1);
    await swipeLeft(page, rows.first());
    await rows.first().locator(".fs-act.del").click();
    await expect(rows).toHaveCount(before);
    await page.reload();
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(600);
    expect(await page.locator("#view .ss .dot").count()).toBe(moments);
  });
});

test.describe("a tap on a message's own words", () => {
  test.use({ storageState: stateFor("moves") });

  test("lights what that message named, and costs no turn", async ({ page }) => {
    await page.goto("/personal/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(600);
    const bubble = page.locator(".bub.coach").last();
    const before = (await page.locator("#chat-screen .pic").boundingBox())!;
    await bubble.click({ position: { x: 6, y: 6 } });
    await page.waitForTimeout(300);
    // what the message named is lit on the picture; with a cluster open the
    // drawing carries no words at all (owner, 2026-09-09), only lit dots
    expect(await page.locator("#view .dot.lit").count()).toBeGreaterThan(0);
    // nothing entered the composer, and nothing above the chat moved
    expect(await page.locator("#composer").innerText()).toBe("");
    const after = (await page.locator("#chat-screen .pic").boundingBox())!;
    expect(after.height).toBe(before.height);
  });

  test("never writes more than three rows of words", async ({ page }) => {
    await page.goto("/personal/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(600);
    await page.locator(".bub.coach").last().click({ position: { x: 6, y: 6 } });
    await page.waitForTimeout(300);
    expect(await page.locator("#view .ss-t").count()).toBeLessThanOrEqual(3);
  });
});
