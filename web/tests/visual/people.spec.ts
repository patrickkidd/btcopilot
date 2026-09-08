import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The list behind the picture, and the button that opens it.
 *
 * The button sits inside the picture, in the same circle as the one beside the
 * message bar: the list button belongs to the thing it lists. The list itself
 * is two ways into one record — what happened, and who it happened to. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const openList = async (page: Page) => {
  await page.locator("#menu-open").click();
  await expect(page.locator("#menu-screen")).toBeVisible();
};

test.describe("the button that opens the list", () => {
  test.use({ storageState: stateFor("moves") });

  test("sits inside the picture, dressed like the sessions button", async ({
    page,
  }) => {
    await settle(page);
    const where = await page.evaluate(() => {
      const button = document.getElementById("menu-open")!;
      const picture = document.querySelector(".pic")!;
      const sessions = document.getElementById("sessions-open")!;
      const box = button.getBoundingClientRect();
      const round = (n: HTMLElement) => {
        const mark = getComputedStyle(n, "::before");
        return `${mark.width} ${mark.height} ${mark.borderRadius} ${mark.borderTopWidth}`;
      };
      return {
        inside: picture.contains(button),
        inTitleRow: !!document.querySelector(".titlerow #menu-open"),
        size: [Math.round(box.width), Math.round(box.height)],
        same: round(button) === round(sessions),
      };
    });
    expect(where.inside).toBe(true);
    expect(where.inTitleRow).toBe(false);
    expect(where.size).toEqual([44, 44]);
    expect(where.same).toBe(true);
  });
});

test.describe("the two lists behind it", () => {
  test.use({ storageState: stateFor("moves") });

  test("open on events, and people are a tap away", async ({ page }) => {
    await settle(page);
    await openList(page);
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(page.locator("#menu-body .row").first()).toBeVisible();

    await page.locator("#tab-people").click();
    await expect(page.locator("#tab-people")).toHaveClass(/on/);
    await expect(page.locator("#menu-add")).toHaveText("+ Add someone");
    // the moves record holds three people
    await expect(page.locator("#menu-body .row")).toHaveCount(3);
    await expect(page.locator("#menu-body .row").first()).toContainText("Ada");
  });

  test("a person opens the editor on the fields the record keeps", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await page.locator("#menu-body .row").first().click();

    const editor = page.locator("#menu-body .editor");
    await expect(editor).toBeVisible();
    await expect(editor.locator('[data-name="name"]')).toHaveValue("Ada");
    await expect(editor.locator('.segs[data-name="gender"] .seg')).toHaveCount(5);
    await expect(editor.locator(".save")).toBeVisible();
    await expect(editor.locator(".del")).toBeVisible();
  });

  test("a name typed in the editor is on the record after saving", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await page.locator("#menu-body .row").first().click();
    await page.locator("#menu-body .editor [data-name=\"last_name\"]").fill("Ellis");
    await page.locator("#menu-body .editor .save").click();
    await expect(page.locator("#menu-body .editor")).toHaveCount(0);
    await expect(page.locator("#menu-body .row").first()).toContainText("Ellis");
  });

  test("the people list orders by birth until the reader asks for names", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await expect(page.locator("#menu-body .div")).toContainText("by birth");
    await page.locator("#menu-body [data-order]").click();
    await expect(page.locator("#menu-body .div")).toContainText("by name");
  });
});

test.describe("the picture", () => {
  test.use({ storageState: stateFor("moves") });

  test("never says it is behind the conversation", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#fresh")).toHaveCount(0);
    await expect(page.locator(".fresh")).toHaveCount(0);
  });
});
