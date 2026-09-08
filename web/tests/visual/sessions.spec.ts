import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The session door: the button beside the message box and the family-sections
 * sheet it raises. */

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
    const sheet = (await page.locator(".fs-sheet").boundingBox())!;
    expect(Math.round(sheet.height)).toBe(Math.round(frame.height * 0.92));
    await expect(page.locator(".fs-grab")).toBeVisible();
    await expect(page.locator(".fs-search input")).toHaveAttribute(
      "placeholder",
      "Search sessions and families",
    );
    const field = (await page.locator(".fs-search input").boundingBox())!;
    expect(Math.round(field.height)).toBe(44);
  });

  test("it lists the family and its sessions, and marks the current one", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    await expect(page.locator(".fs-fhead .fs-fname")).not.toBeEmpty();
    await expect(page.locator(".fs-body .row").first()).toBeVisible();
    await expect(page.locator(".fs-body .row.cur")).toHaveCount(1);
    await expect(page.locator(".fs-new")).toContainText("New session with");
  });

  test("a search that matches nothing says so, in those words", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator(".fs-search input").fill("zzzzz-no-such-session");
    await expect(page.locator(".fs-hint")).toHaveText("No sessions match");
  });

  test("tapping the scrim closes it", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator(".fs-scrim").click({ position: { x: 195, y: 20 } });
    await page.waitForTimeout(400);
    await expect(page.locator(".fs-sheet")).toBeHidden();
  });

  test("every row and control in the sheet meets the 44px floor", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const small = await page.evaluate(() =>
      [
        ...document.querySelectorAll(
          ".fs-sheet button, .fs-sheet input, .fs-body .row, .fs-more",
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
});
