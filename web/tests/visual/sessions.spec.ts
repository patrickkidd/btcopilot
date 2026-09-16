import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The session door: the button beside the message box and the family-sections
 * sheet it raises. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
};

const openSheet = async (page: Page) => {
  await page.locator("#sessions-open").click();
  await expect(page.locator("#sessions-sheet")).toBeVisible();
  await page.waitForTimeout(400);
};

test.describe("the sessions sheet", () => {
  test.use({ storageState: stateFor("moves") });

  test("the button sits in the input bar, not the title row", async ({ page }) => {
    await settle(page);
    const button = page.locator("#sessions-open");
    await expect(button).toBeVisible();
    const inBar = await button.evaluate((node) => !!node.closest(".inbar"));
    expect(inBar).toBe(true);
    const box = (await button.boundingBox())!;
    expect(Math.round(box.width)).toBe(44);
    expect(Math.round(box.height)).toBe(44);
  });

  test("it opens to 92% of the frame with a grabber and a search field", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const frame = (await page.locator(".app").boundingBox())!;
    const sheet = (await page.locator("#sessions-sheet").boundingBox())!;
    expect(Math.round(sheet.height)).toBe(Math.round(frame.height * 0.92));
    // the page holds several sheets of this class; only this one is the sessions'
    await expect(page.locator("#sessions-sheet .fs-grab")).toBeVisible();
    // R-0347: the sheet lists only this family's sessions, so it searches sessions
    await expect(page.locator("#sessions-sheet .fs-search input")).toHaveAttribute(
      "placeholder",
      "Search sessions",
    );
    const field = (await page.locator("#sessions-sheet .fs-search input").boundingBox())!;
    expect(Math.round(field.height)).toBe(44);
  });

  test("it lists the sessions under a day heading, and marks the current one", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    await expect(page.locator("#sessions-sheet .fs-body .ghead").first()).not.toBeEmpty();
    await expect(page.locator("#sessions-sheet .fs-body .row").first()).toBeVisible();
    await expect(page.locator("#sessions-sheet .fs-body .row.cur")).toHaveCount(1);
    // the foot also carries the upload and note buttons of the same class
    await expect(page.locator("#sessions-sheet .fs-new").first()).toContainText(
      "New session with",
    );
  });

  test("a search that matches nothing says so, in those words", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator("#sessions-sheet .fs-search input").fill("zzzzz-no-such-session");
    await expect(page.locator(".fs-hint")).toHaveText("No sessions match");
  });

  test("tapping the scrim closes it", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator("#sessions-scrim").click({ position: { x: 195, y: 20 } });
    await page.waitForTimeout(400);
    await expect(page.locator("#sessions-sheet")).toBeHidden();
  });

  test("every row and control in the sheet meets the 44px floor", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const small = await page.evaluate(() =>
      [
        ...document.querySelectorAll(
          ".fs-sheet button, .fs-sheet input, .fs-body .row",
        ),
      ]
        .map((node) => ({
          what: node.className || node.tagName,
          height: Math.round(node.getBoundingClientRect().height),
        }))
        .filter((row) => row.height > 0 && row.height < 44),
    );
    expect(small).toEqual([]);
  });

  /** A reader without the professional licence never meets the word case, and
   * the plus beside a family starts a session on that family [R-0285]. */
  test("the sheet never says case, and each family carries its own plus", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const sheet = page.locator("#sessions-sheet");
    expect(await sheet.innerText()).not.toMatch(/\bcases?\b/i);
    // the family is chosen on the account page, never here (R-0347)
    await expect(page.locator(".fs-fhead")).toHaveCount(0);
  });
});
